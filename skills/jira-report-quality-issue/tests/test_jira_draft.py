from __future__ import annotations

import copy
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from jira_draft import DraftError, canonicalize_draft


def png_bytes(width: int = 1, height: int = 1) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind)
        crc = zlib.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scanline = b"\x00" + b"\x00\x00\x00" * width
    raw = scanline * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def draft(path: Path) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "context": {
            "repository": "example/repo",
            "branch": "feature/x",
            "commit": "abc123",
            "task": "Save dialog",
        },
        "issues": [
            {
                "summary": "Save dialog: request failure is hidden",
                "description": {
                    "background": "Saving a model must report failures.",
                    "actualBehavior": "The dialog closes after a failed request.",
                    "expectedBehavior": "The dialog stays open and shows the failure.",
                    "impact": "Users believe unsaved work is persisted.",
                    "reproductionSteps": [
                        "Open the dialog",
                        "Force the request to fail",
                    ],
                    "evidence": ["src/save.ts and focused test failure"],
                    "affectedScope": ["src/save.ts"],
                    "verification": ["Focused test reproduced the failure"],
                    "limitations": [],
                    "suggestedDirection": "Keep the dialog open until confirmed success.",
                },
                "priority": "High",
                "components": ["Frontend"],
                "environment": "Test environment",
                "fixVersions": ["Future"],
                "labels": ["quality"],
                "customFields": {},
                "qualityReview": {
                    "approved": True,
                    "notes": "Confirmed in scope with a focused test.",
                },
                "safetyReview": {
                    "approved": True,
                    "notes": "Payload contains only repository-relative evidence.",
                },
                "screenshots": [
                    {
                        "path": str(path),
                        "description": "Failed save closes the dialog",
                        "visualReview": {
                            "approved": True,
                            "notes": "Viewed; relevant and no sensitive content.",
                        },
                    }
                ],
                "duplicateReview": None,
            }
        ],
    }


class DraftTests(unittest.TestCase):
    def test_fingerprint_excludes_local_path_and_approval_field(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_dir,
            tempfile.TemporaryDirectory() as second_dir,
        ):
            first = Path(first_dir) / "one.png"
            second = Path(second_dir) / "two.png"
            first.write_bytes(png_bytes())
            second.write_bytes(png_bytes())
            first_draft = draft(first)
            second_draft = draft(second)
            second_draft["approvedBatchFingerprint"] = "ignored-until-checked-by-cli"
            first_plan = canonicalize_draft(
                first_draft, default_project_key="TEST", default_issue_type="Bug"
            )
            second_plan = canonicalize_draft(
                second_draft, default_project_key="TEST", default_issue_type="Bug"
            )

        self.assertEqual(
            first_plan["batchFingerprint"], second_plan["batchFingerprint"]
        )
        self.assertNotEqual(
            first_plan["issues"][0]["screenshots"][0]["path"],
            second_plan["issues"][0]["screenshots"][0]["path"],
        )

    def test_modified_screenshot_changes_batch_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.png"
            path.write_bytes(png_bytes())
            raw = draft(path)
            first = canonicalize_draft(
                raw, default_project_key="TEST", default_issue_type="Bug"
            )
            path.write_bytes(png_bytes(width=2))
            second = canonicalize_draft(
                copy.deepcopy(raw), default_project_key="TEST", default_issue_type="Bug"
            )

        self.assertNotEqual(first["batchFingerprint"], second["batchFingerprint"])

    def test_environment_and_fix_versions_change_batch_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.png"
            path.write_bytes(png_bytes())
            raw = draft(path)
            first = canonicalize_draft(
                raw, default_project_key="TEST", default_issue_type="Bug"
            )
            changed = copy.deepcopy(raw)
            changed["issues"][0]["environment"] = "Production"
            changed["issues"][0]["fixVersions"] = ["Next"]
            second = canonicalize_draft(
                changed, default_project_key="TEST", default_issue_type="Bug"
            )

        self.assertNotEqual(first["batchFingerprint"], second["batchFingerprint"])

    def test_env_defaults_apply_only_when_issue_fields_are_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.png"
            path.write_bytes(png_bytes())
            omitted = draft(path)
            del omitted["issues"][0]["components"]
            del omitted["issues"][0]["fixVersions"]
            defaulted = canonicalize_draft(
                omitted,
                default_project_key="TEST",
                default_issue_type="Bug",
                default_components=("Configured Component",),
                default_fix_versions=("Configured Future",),
            )
            explicit = draft(path)
            explicit["issues"][0]["components"] = []
            explicit["issues"][0]["fixVersions"] = []
            overridden = canonicalize_draft(
                explicit,
                default_project_key="TEST",
                default_issue_type="Bug",
                default_components=("Configured Component",),
                default_fix_versions=("Configured Future",),
            )

        self.assertEqual(defaulted["issues"][0]["components"], ["Configured Component"])
        self.assertEqual(defaulted["issues"][0]["fixVersions"], ["Configured Future"])
        self.assertEqual(overridden["issues"][0]["components"], [])
        self.assertEqual(overridden["issues"][0]["fixVersions"], [])

    def test_requires_completed_visual_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.png"
            path.write_bytes(png_bytes())
            raw = draft(path)
            raw["issues"][0]["screenshots"][0]["visualReview"]["approved"] = False
            with self.assertRaisesRegex(DraftError, "visualReview"):
                canonicalize_draft(
                    raw, default_project_key="TEST", default_issue_type="Bug"
                )


if __name__ == "__main__":
    unittest.main()
