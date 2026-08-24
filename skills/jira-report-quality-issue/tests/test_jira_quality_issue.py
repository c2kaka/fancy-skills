from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from jira_api import (
    ApiError,
    Deployment,
    HttpResult,
    JiraConfig,
    OutcomeUnknownError,
    build_create_fields,
)
from jira_quality_issue import (
    WorkflowFailure,
    apply_new,
    main,
    resume_attachments,
    run_preflight,
    verify_operation,
)
from jira_state import read_state


def png_bytes() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind)
        crc = zlib.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )


def draft(path: Path) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "context": {
            "repository": "example/repo",
            "branch": "feature/x",
            "commit": "abc",
            "task": "Save",
        },
        "issues": [
            {
                "summary": "Save dialog: failed request closes the dialog",
                "description": {
                    "background": "The save dialog persists a model.",
                    "actualBehavior": "A failed request closes the dialog.",
                    "expectedBehavior": "The dialog remains open and shows the error.",
                    "impact": "Users can lose unsaved work.",
                    "reproductionSteps": ["Open save", "Return HTTP 500"],
                    "evidence": ["src/save.ts and focused test"],
                    "affectedScope": ["src/save.ts"],
                    "verification": ["Focused failure reproduced"],
                    "limitations": [],
                    "suggestedDirection": "Close only after confirmed success.",
                },
                "priority": "High",
                "components": ["Frontend"],
                "environment": "Test environment",
                "fixVersions": ["Future"],
                "labels": ["quality"],
                "customFields": {},
                "qualityReview": {"approved": True, "notes": "Confirmed and in scope."},
                "safetyReview": {
                    "approved": True,
                    "notes": "No secrets or private paths in JIRA text.",
                },
                "screenshots": [
                    {
                        "path": str(path),
                        "description": "The dialog disappears after HTTP 500",
                        "visualReview": {"approved": True, "notes": "Viewed and safe."},
                    }
                ],
                "duplicateReview": None,
            }
        ],
    }


class FakeClient:
    def __init__(
        self,
        *,
        upload_unknown: bool = False,
        upload_failure: bool = False,
        create_unknown: bool = False,
        recover_unknown_create: bool = False,
        candidates: list[dict[str, object]] | None = None,
    ):
        self.deployment = Deployment(kind="server", api_version=2, raw_type="Server")
        self.upload_unknown = upload_unknown
        self.upload_failure = upload_failure
        self.create_unknown = create_unknown
        self.recover_unknown_create = recover_unknown_create
        self.candidates = candidates or []
        self.create_calls = 0
        self.upload_calls = 0
        self.created_fields: dict[str, object] | None = None
        self.attachments: list[dict[str, object]] = []

    def detect_deployment(self) -> Deployment:
        return self.deployment

    def current_user(self, _deployment: Deployment) -> dict[str, object]:
        return {"name": "owner", "displayName": "Owner", "active": True}

    def permissions(
        self, _deployment: Deployment, _project_key: str
    ) -> dict[str, object]:
        names = (
            "BROWSE_PROJECTS",
            "CREATE_ISSUES",
            "ASSIGN_ISSUES",
            "ASSIGNABLE_USER",
            "CREATE_ATTACHMENTS",
        )
        return {"permissions": {name: {"havePermission": True} for name in names}}

    def attachment_meta(self, _deployment: Deployment) -> dict[str, object]:
        return {"enabled": True, "uploadLimit": 10_000_000}

    def create_metadata(
        self, _deployment: Deployment, project_key: str, issue_type: str
    ) -> dict[str, object]:
        return {
            "projectKey": project_key,
            "issueType": {"name": issue_type},
            "fields": {
                "project": {"required": True},
                "issuetype": {"required": True},
                "summary": {"required": True},
                "description": {"required": True},
                "assignee": {"required": True},
                "priority": {"allowedValues": [{"name": "High"}]},
                "components": {"allowedValues": [{"name": "Frontend"}]},
                "environment": {"required": True},
                "fixVersions": {
                    "required": True,
                    "allowedValues": [{"name": "Future"}],
                },
                "labels": {},
            },
        }

    def search_candidates(
        self, _deployment: Deployment, _project: str, _issue_type: str
    ) -> list[dict[str, object]]:
        return self.candidates

    def search_fingerprint(
        self, _deployment: Deployment, _project: str, _fingerprint: str
    ) -> list[dict[str, object]]:
        if self.recover_unknown_create and self.create_calls > 0:
            return [{"key": "TEST-1"}]
        return []

    def create_issue(
        self,
        deployment: Deployment,
        issue: dict[str, object],
        current_user: dict[str, object],
        metadata: dict[str, object],
    ) -> HttpResult:
        self.create_calls += 1
        self.created_fields = build_create_fields(
            deployment, issue, current_user, metadata
        )
        if self.create_unknown:
            raise OutcomeUnknownError("simulated create timeout")
        return HttpResult(status=201, headers={}, data={"id": "10001", "key": "TEST-1"})

    def get_issue(
        self, _deployment: Deployment, _key: str, *, extra_fields: tuple[str, ...] = ()
    ) -> dict[str, object]:
        del extra_fields
        if self.created_fields is None:
            raise AssertionError("get_issue called before create")
        fields = self.created_fields
        return {
            "key": "TEST-1",
            "fields": {
                "project": fields["project"],
                "issuetype": fields["issuetype"],
                "summary": fields["summary"],
                "description": fields["description"],
                "reporter": {"name": "owner"},
                "assignee": fields["assignee"],
                "priority": fields.get("priority"),
                "components": fields.get("components", []),
                "environment": fields.get("environment"),
                "fixVersions": fields.get("fixVersions", []),
                "labels": fields.get("labels", []),
                "attachment": list(self.attachments),
            },
        }

    def upload_attachment(
        self,
        _deployment: Deployment,
        _key: str,
        file_path: Path,
        upload_name: str,
        mime_type: str,
    ) -> HttpResult:
        self.upload_calls += 1
        if self.upload_unknown:
            raise OutcomeUnknownError("simulated timeout")
        if self.upload_failure:
            raise ApiError("simulated definitive failure", status=413)
        attachment = {
            "id": "20001",
            "filename": upload_name,
            "size": file_path.stat().st_size,
            "mimeType": mime_type,
        }
        self.attachments.append(attachment)
        return HttpResult(status=200, headers={}, data=[attachment])


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = JiraConfig(
            "https://jira.example.com", "owner", "secret", "TEST", "Bug"
        )

    def test_happy_path_creates_once_uploads_once_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screenshot = root / "proof.png"
            screenshot.write_bytes(png_bytes())
            client = FakeClient()
            preflight = run_preflight(draft(screenshot), self.config, client)
            result = apply_new(preflight, self.config, client, root / ".state")
            state_text = (root / ".state" / f"{result['operationId']}.json").read_text(
                encoding="utf-8"
            )
            state = read_state(root / ".state", str(preflight["operationId"]))

        self.assertTrue(preflight["ready"])
        self.assertEqual(result["status"], "verified")
        self.assertEqual(client.create_calls, 1)
        self.assertEqual(client.upload_calls, 1)
        self.assertNotIn(str(screenshot), state_text)
        self.assertIn("environment", result["issues"][0])
        self.assertEqual(result["issues"][0]["fixVersions"], ["Future"])
        verification_fields = state["issues"][0]["verification"]["fieldHashes"]
        self.assertIn("environment", verification_fields)
        self.assertIn("fixVersions", verification_fields)

    def test_preflight_uses_env_component_and_fix_version_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            screenshot = Path(directory) / "proof.png"
            screenshot.write_bytes(png_bytes())
            raw = draft(screenshot)
            del raw["issues"][0]["components"]
            del raw["issues"][0]["fixVersions"]
            config = JiraConfig(
                "https://jira.example.com",
                "owner",
                "secret",
                "TEST",
                "Bug",
                components=("Frontend",),
                fix_versions=("Future",),
            )
            preflight = run_preflight(raw, config, FakeClient())

        self.assertTrue(preflight["ready"])
        issue = preflight["canonicalPlan"]["issues"][0]
        self.assertEqual(issue["components"], ["Frontend"])
        self.assertEqual(issue["fixVersions"], ["Future"])
        self.assertEqual(
            preflight["issues"][0]["createFields"]["fixVersions"],
            [{"name": "Future"}],
        )

    def test_unknown_attachment_stops_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screenshot = root / "proof.png"
            screenshot.write_bytes(png_bytes())
            client = FakeClient(upload_unknown=True)
            preflight = run_preflight(draft(screenshot), self.config, client)
            with self.assertRaises(WorkflowFailure) as caught:
                apply_new(preflight, self.config, client, root / ".state")
            state = read_state(root / ".state", str(preflight["operationId"]))

        self.assertEqual(caught.exception.status, "attachment_outcome_unknown")
        self.assertEqual(client.create_calls, 1)
        self.assertEqual(client.upload_calls, 1)
        self.assertEqual(state["status"], "attachment_outcome_unknown")

    def test_unknown_create_recovers_by_fingerprint_without_second_post(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screenshot = root / "proof.png"
            screenshot.write_bytes(png_bytes())
            client = FakeClient(create_unknown=True, recover_unknown_create=True)
            preflight = run_preflight(draft(screenshot), self.config, client)
            result = apply_new(preflight, self.config, client, root / ".state")

        self.assertEqual(result["status"], "verified")
        self.assertEqual(client.create_calls, 1)

    def test_unknown_create_without_fingerprint_match_stops_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screenshot = root / "proof.png"
            screenshot.write_bytes(png_bytes())
            client = FakeClient(create_unknown=True)
            preflight = run_preflight(draft(screenshot), self.config, client)
            with self.assertRaises(WorkflowFailure) as caught:
                apply_new(preflight, self.config, client, root / ".state")

        self.assertEqual(caught.exception.status, "creation_outcome_unknown")
        self.assertEqual(client.create_calls, 1)

    def test_definitely_missing_attachment_can_resume_with_new_fingerprint(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screenshot = root / "proof.png"
            screenshot.write_bytes(png_bytes())
            raw = draft(screenshot)
            client = FakeClient(upload_failure=True)
            preflight = run_preflight(raw, self.config, client)
            with self.assertRaises(WorkflowFailure):
                apply_new(preflight, self.config, client, root / ".state")
            verified = verify_operation(
                self.config, client, root / ".state", str(preflight["operationId"])
            )
            raw["approvedResumeFingerprint"] = verified["resumeFingerprint"]
            client.upload_failure = False
            resumed = resume_attachments(
                raw,
                self.config,
                client,
                root / ".state",
                str(preflight["operationId"]),
                str(verified["resumeFingerprint"]),
            )

        self.assertEqual(len(verified["resumePlan"]), 1)
        self.assertEqual(resumed["status"], "verified")
        self.assertEqual(client.create_calls, 1)
        self.assertEqual(client.upload_calls, 2)

    def test_duplicate_candidates_block_until_semantic_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            screenshot = Path(directory) / "proof.png"
            screenshot.write_bytes(png_bytes())
            client = FakeClient(
                candidates=[
                    {
                        "key": "TEST-9",
                        "summary": "Possible duplicate",
                        "status": "Open",
                        "updated": "now",
                    }
                ]
            )
            preflight = run_preflight(draft(screenshot), self.config, client)

        self.assertFalse(preflight["ready"])
        self.assertEqual(preflight["blockers"][0]["code"], "duplicate_review_required")

    def test_confirmation_mismatch_exits_before_loading_blank_env(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            draft_path = Path(directory) / "draft.json"
            draft_path.write_text(
                json.dumps({"approvedBatchFingerprint": "expected"}), encoding="utf-8"
            )
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    ["apply", "--draft", str(draft_path), "--confirm", "different"]
                )

        self.assertEqual(exit_code, 3)
        self.assertEqual(
            json.loads(output.getvalue())["status"], "confirmation_mismatch"
        )


if __name__ == "__main__":
    unittest.main()
