from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from video_common import (
    VideoInsightError,
    extract_json_payload,
    parse_video_target,
    resolve_within,
    tool_version,
)


class VideoCommonTests(unittest.TestCase):
    def test_tool_version_timeout_is_reported_as_unavailable(self) -> None:
        with (
            patch("video_common.command_path", return_value="/tmp/example-tool"),
            patch(
                "video_common.subprocess.run",
                side_effect=subprocess.TimeoutExpired("example-tool", 15),
            ),
        ):
            result = tool_version("example-tool")
        self.assertFalse(result["available"])
        self.assertIn("error", result)

    def test_parses_supported_video_urls(self) -> None:
        youtube = parse_video_target("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        bilibili = parse_video_target("https://www.bilibili.com/video/BV1xx411c7mD")
        self.assertEqual(
            (youtube.platform, youtube.video_id), ("youtube", "dQw4w9WgXcQ")
        )
        self.assertEqual(
            (bilibili.platform, bilibili.video_id), ("bilibili", "BV1xx411c7mD")
        )

    def test_rejects_playlist_and_unknown_host(self) -> None:
        with self.assertRaises(VideoInsightError):
            parse_video_target("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123")
        with self.assertRaises(VideoInsightError):
            parse_video_target("https://example.com/video/123")

    def test_extracts_json_from_noisy_cli_output(self) -> None:
        value = extract_json_payload(
            'notice: update available\n[{"from": 0, "to": 1, "content": "hello"}]\nmore'
        )
        self.assertEqual(value[0]["content"], "hello")

    def test_rejects_symlinked_report_resource(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / f"{root.name}-outside.txt"
            outside.write_text("secret", encoding="utf-8")
            link = root / "link.txt"
            link.symlink_to(outside)
            try:
                with self.assertRaises(VideoInsightError):
                    resolve_within(link, root, must_exist=True)
            finally:
                outside.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
