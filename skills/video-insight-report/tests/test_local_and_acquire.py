from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import acquire_video
import local_transcribe
from video_common import VideoInsightError


class LocalTranscriptionTests(unittest.TestCase):
    def test_preflight_never_claims_cloud(self) -> None:
        result = local_transcribe.preflight_result(local_transcribe.DEFAULT_MODEL)
        self.assertFalse(result["cloud_used"])
        self.assertIn(result["status"], {"READY", "CONFIRMATION_REQUIRED"})

    def test_missing_runtime_or_model_requires_explicit_download_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "audio.wav"
            audio.write_bytes(b"not-real-audio")
            args = argparse.Namespace(
                audio=str(audio),
                output=str(Path(directory) / "out.json"),
                model=local_transcribe.DEFAULT_MODEL,
                language=None,
                timeout=1,
                allow_model_download=False,
            )
            state = {
                "supported_architecture": True,
                "model_available": False,
            }
            with (
                patch.object(local_transcribe, "preflight_result", return_value=state),
                patch.object(
                    local_transcribe,
                    "runtime_command",
                    return_value=(["uvx", "mlx_whisper"], False),
                ),
                self.assertRaises(VideoInsightError),
            ):
                local_transcribe.transcribe(args)


class AcquisitionTests(unittest.TestCase):
    def test_subtitle_diagnostic_redacts_urls_and_credentials(self) -> None:
        value = acquire_video.safe_diagnostic(
            "fetch https://example.com/caption?sig=secret SESSDATA=private-value"
        )
        self.assertNotIn("secret", value)
        self.assertNotIn("private-value", value)
        self.assertIn("[URL_REDACTED]", value)
        self.assertIn("[REDACTED]", value)

    def test_normalizes_nested_bilibili_metadata(self) -> None:
        raw = {
            "ok": True,
            "data": {
                "video": {
                    "bvid": "BV1xx411c7mD",
                    "title": "A video",
                    "duration_seconds": 12,
                    "url": "https://www.bilibili.com/video/BV1xx411c7mD",
                    "owner": {"name": "Creator"},
                }
            },
        }
        value = acquire_video.normalize_metadata(
            raw, "bilibili", "https://www.bilibili.com/video/BV1xx411c7mD"
        )
        self.assertEqual(value["video_id"], "BV1xx411c7mD")
        self.assertEqual(value["creator"], "Creator")
        self.assertEqual(value["duration_seconds"], 12)

    def test_empty_bilibili_subtitle_payload_is_not_usable(self) -> None:
        empty = {
            "data": {
                "subtitle": {
                    "available": False,
                    "items": [],
                    "text": "",
                }
            }
        }
        usable = [{"from": 1.0, "to": 2.0, "content": "A caption"}]
        self.assertFalse(acquire_video.has_timeline_segments(empty))
        self.assertTrue(acquire_video.has_timeline_segments(usable))

    def test_bilibili_video_download_uses_opencli_not_direct_ytdlp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            captured: list[str] = []

            def fake_run(
                command: list[str], **_: object
            ) -> subprocess.CompletedProcess[str]:
                captured.extend(command)
                output_dir = Path(command[command.index("--output") + 1])
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "video.mp4").write_bytes(b"video")
                return subprocess.CompletedProcess(command, 0, "{}", "")

            args = argparse.Namespace(
                url="https://www.bilibili.com/video/BV1xx411c7mD",
                run_dir=str(run_dir),
                allow_download=True,
                timeout=10,
                quality="720p",
            )
            with (
                patch.object(acquire_video, "run_command", side_effect=fake_run),
                patch.object(
                    acquire_video, "require_tool", side_effect=lambda name: name
                ),
            ):
                result = acquire_video.download_video(args)
            self.assertEqual(result["status"], "READY")
            self.assertEqual(captured[0:3], ["opencli", "bilibili", "download"])
            self.assertNotIn("yt-dlp", captured)

    def test_download_requires_explicit_flag(self) -> None:
        args = argparse.Namespace(
            url="https://youtu.be/dQw4w9WgXcQ",
            run_dir="/tmp/unused",
            allow_download=False,
        )
        with self.assertRaises(VideoInsightError):
            acquire_video.download_audio(args)


if __name__ == "__main__":
    unittest.main()
