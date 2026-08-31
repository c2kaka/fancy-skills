from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from image_evidence import inspect_image
from video_common import VideoInsightError, load_json
from video_insight import (
    extract_frames,
    initialize,
    normalize,
    render,
    validate,
    validate_manifest,
)

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def init_args(root: Path, title: str = "Test video") -> argparse.Namespace:
    return argparse.Namespace(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        question=["What is the core claim?"],
        output_root=str(root),
        depth="standard",
        output_language="en",
        source_language="en",
        title=title,
        creator="Tester",
        duration_seconds=60.0,
    )


class VideoInsightTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "ffmpeg and ffprobe are required",
    )
    def test_extracts_real_frame_from_synthetic_video(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "synthetic.mp4"
            subprocess.run(
                [
                    shutil.which("ffmpeg") or "ffmpeg",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=red:s=64x48:d=2:r=5",
                    "-c:v",
                    "mpeg4",
                    "-y",
                    str(video),
                ],
                check=True,
                timeout=30,
            )
            plan = root / "plan.json"
            plan.write_text(
                json.dumps(
                    {
                        "evidence": [
                            {
                                "id": "red-frame",
                                "time_seconds": 1,
                                "claim": "The frame is red.",
                                "confidence": "high",
                                "quote": "Unverified planned text",
                                "quote_kind": "on_screen_text",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            report_dir = root / "report"
            result = extract_frames(
                argparse.Namespace(
                    video=str(video),
                    plan=str(plan),
                    report_dir=str(report_dir),
                    timeout=30,
                )
            )
            payload = load_json(Path(result["path"]))
            image = payload["evidence"][0]["raw_image"]
            self.assertEqual(result["frames"], 1)
            self.assertEqual(image["width"], 64)
            self.assertEqual(image["height"], 48)
            self.assertEqual(image["mime_type"], "image/png")
            self.assertTrue((report_dir / image["path"]).is_file())
            self.assertEqual(payload["evidence"][0]["quote"], "")
            self.assertEqual(payload["evidence"][0]["quote_kind"], "none")
            self.assertEqual(
                payload["evidence"][0]["planned_quote"], "Unverified planned text"
            )
            self.assertNotIn(str(video), json.dumps(payload))

    def test_normalizes_vtt_and_merges_exact_duplicate_cues(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.vtt"
            source.write_text(
                "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<b>Hello</b> world\n\n"
                "00:00:01.900 --> 00:00:03.000\nHello world\n\n"
                "00:00:04.000 --> 00:00:05.000\nNext idea\n",
                encoding="utf-8",
            )
            output = root / "transcript.json"
            result = normalize(
                argparse.Namespace(
                    input=str(source),
                    output=str(output),
                    source_kind="subtitle",
                    language="en",
                )
            )
            self.assertEqual(result["segments"], 2)
            payload = load_json(output)
            self.assertEqual(payload["segments"][0]["end_seconds"], 3.0)

    def test_renders_incomplete_report_and_escapes_untrusted_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = initialize(init_args(root, title="<script>alert(1)</script>"))
            manifest_path = Path(result["manifest"])
            rendered = render(
                argparse.Namespace(
                    manifest=str(manifest_path), output=None, self_contained=False
                )
            )
            content = Path(rendered["html"]).read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", content)
            self.assertNotIn("<script>", content.lower())
            self.assertIn(">INCOMPLETE<", content)

    def test_renders_built_in_chinese_interface_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = init_args(Path(directory))
            args.output_language = "zh-CN"
            result = initialize(args)
            rendered = render(
                argparse.Namespace(
                    manifest=result["manifest"], output=None, self_contained=False
                )
            )
            content = Path(rendered["html"]).read_text(encoding="utf-8")
            self.assertIn("金字塔总结", content)
            self.assertIn("第一性原理分析", content)
            self.assertIn("目录", content)
            self.assertIn('dir="auto"', content)

    def test_renders_english_interface_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = initialize(init_args(Path(directory)))
            rendered = render(
                argparse.Namespace(
                    manifest=result["manifest"], output=None, self_contained=False
                )
            )
            content = Path(rendered["html"]).read_text(encoding="utf-8")
            self.assertIn("Pyramid summary", content)
            self.assertIn("First-principles analysis", content)
            self.assertIn("Contents", content)

    def test_escapes_custom_interface_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = initialize(init_args(Path(directory)))
            manifest_path = Path(result["manifest"])
            manifest = load_json(manifest_path)
            manifest["request"]["ui_labels"] = {
                "contents": '<script data-test="label">alert(1)</script>'
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            rendered = render(
                argparse.Namespace(
                    manifest=str(manifest_path), output=None, self_contained=False
                )
            )
            content = Path(rendered["html"]).read_text(encoding="utf-8")
            self.assertIn(
                "&lt;script data-test=&quot;label&quot;&gt;alert(1)&lt;/script&gt;",
                content,
            )
            self.assertNotIn('<script data-test="label">', content)

    def complete_manifest(self, root: Path) -> tuple[Path, dict]:
        result = initialize(init_args(root))
        manifest_path = Path(result["manifest"])
        manifest = load_json(manifest_path)
        image_path = manifest_path.parent / "evidence" / "raw" / "claim-1.png"
        image_path.write_bytes(PNG_1X1)
        image = {"path": "evidence/raw/claim-1.png", **inspect_image(image_path)}
        manifest["status"] = "COMPLETE"
        manifest["pyramid"] = {
            "top": "The top conclusion.",
            "supports": [
                {"title": "Support", "summary": "Reason", "evidence_ids": ["claim-1"]}
            ],
        }
        manifest["chapters"] = [
            {"start_seconds": 0, "end_seconds": 60, "title": "Whole", "summary": "Map"}
        ]
        manifest["evidence"] = [
            {
                "id": "claim-1",
                "claim": "A supported claim",
                "start_seconds": 5,
                "end_seconds": 8,
                "quote": "Short quote",
                "quote_kind": "subtitle",
                "speaker": "Speaker 1",
                "confidence": "high",
                "raw_image": image,
                "derived_image": None,
                "rationale": "The frame and quote support it.",
                "source_kind": "combined",
            }
        ]
        manifest["first_principles"] = {
            "problem": "What problem is solved?",
            "fundamentals": ["Fact"],
            "assumptions": ["Assumption"],
            "mechanism": ["Mechanism"],
            "boundaries": ["Boundary"],
            "rebuilt_conclusion": "Rebuilt conclusion",
            "implications": ["Implication"],
            "open_questions": ["Question"],
        }
        for name in ("metadata", "frames", "analysis"):
            manifest["pipeline"]["stages"][name] = {"status": "COMPLETE"}
        for name in ("captions", "transcription"):
            manifest["pipeline"]["stages"][name] = {"status": "SKIPPED"}
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest_path, manifest

    def test_complete_report_embeds_verified_frame(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path, _ = self.complete_manifest(Path(directory))
            result = render(
                argparse.Namespace(
                    manifest=str(manifest_path), output=None, self_contained=True
                )
            )
            content = Path(result["html"]).read_text(encoding="utf-8")
            self.assertIn("data:image/png;base64,", content)
            self.assertIn(">COMPLETE<", content)
            rendered_manifest = load_json(manifest_path)
            self.assertEqual(
                rendered_manifest["pipeline"]["stages"]["validation"]["status"],
                "PENDING",
            )
            validate(
                argparse.Namespace(manifest=str(manifest_path), html=result["html"])
            )
            validated_manifest = load_json(manifest_path)
            self.assertEqual(
                validated_manifest["pipeline"]["stages"]["validation"]["status"],
                "COMPLETE",
            )

    def test_complete_rejects_low_confidence_only_support(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path, manifest = self.complete_manifest(Path(directory))
            manifest["evidence"][0]["confidence"] = "low"
            with self.assertRaises(VideoInsightError):
                validate_manifest(manifest, manifest_path.parent)

    def test_complete_rejects_pending_core_pipeline_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path, manifest = self.complete_manifest(Path(directory))
            manifest["pipeline"]["stages"]["frames"] = {"status": "PENDING"}
            with self.assertRaises(VideoInsightError):
                validate_manifest(manifest, manifest_path.parent)

    def test_image_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path, manifest = self.complete_manifest(Path(directory))
            manifest["evidence"][0]["raw_image"]["sha256"] = "0" * 64
            with self.assertRaises(VideoInsightError):
                validate_manifest(manifest, manifest_path.parent)


if __name__ == "__main__":
    unittest.main()
