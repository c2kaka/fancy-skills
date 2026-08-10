from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "jira-update"
    / "scripts"
    / "jira_update.py"
)
SPEC = importlib.util.spec_from_file_location("jira_update", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
jira_update = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = jira_update
SPEC.loader.exec_module(jira_update)


class FakeResponse:
    def __init__(self, body: dict[str, object] | None = None):
        self.payload = b"" if body is None else json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.payload


ISSUE = {
    "fields": {
        "status": {"id": "3", "name": "In Progress"},
        "reporter": {"name": "tester", "displayName": "Test User"},
        "assignee": {"name": "developer", "displayName": "Dev User"},
    }
}
TRANSITIONS = {
    "transitions": [
        {
            "id": "81",
            "name": "Send to test",
            "to": {"id": "5", "name": "TEST"},
        }
    ]
}
FINAL_ISSUE = {
    "fields": {
        "status": {"id": "5", "name": "TEST"},
        "reporter": {"name": "tester", "displayName": "Test User"},
        "assignee": {"name": "tester", "displayName": "Test User"},
    }
}


class JiraUpdateTests(unittest.TestCase):
    def setUp(self):
        self.config = jira_update.JiraConfig(
            base_url="https://jira.example.com",
            user="developer",
            password="secret",
        )

    def test_inspect_uses_get_only(self):
        responses = [FakeResponse(ISSUE), FakeResponse(TRANSITIONS)]
        with mock.patch.object(
            jira_update.urllib.request, "urlopen", side_effect=responses
        ) as urlopen:
            result = jira_update.inspect_issue(self.config, "JIRA-1234")

        self.assertEqual(result["available_transitions"][0]["id"], "81")
        self.assertEqual(
            [call.args[0].get_method() for call in urlopen.call_args_list],
            ["GET", "GET"],
        )

    def test_apply_sends_approved_payloads_and_verifies_final_state(self):
        responses = [
            FakeResponse(ISSUE),
            FakeResponse(TRANSITIONS),
            FakeResponse(),
            FakeResponse(),
            FakeResponse(),
            FakeResponse(FINAL_ISSUE),
        ]
        with mock.patch.object(
            jira_update.urllib.request, "urlopen", side_effect=responses
        ) as urlopen:
            result = jira_update.apply_updates(
                self.config,
                "JIRA-1234",
                "修复结果\n- 根因：边界条件错误",
                "81",
                "tester",
            )

        requests = [call.args[0] for call in urlopen.call_args_list]
        self.assertEqual(
            [request.get_method() for request in requests],
            ["GET", "GET", "POST", "POST", "PUT", "GET"],
        )
        self.assertEqual(
            json.loads(requests[2].data.decode("utf-8")),
            {"body": "修复结果\n- 根因：边界条件错误"},
        )
        self.assertEqual(
            json.loads(requests[3].data.decode("utf-8")),
            {"transition": {"id": "81"}},
        )
        self.assertEqual(
            json.loads(requests[4].data.decode("utf-8")), {"name": "tester"}
        )
        self.assertEqual(result["status"], "TEST")
        self.assertEqual(result["assignee"], "tester")

    def test_unknown_transition_fails_before_any_write(self):
        responses = [FakeResponse(ISSUE), FakeResponse(TRANSITIONS)]
        with (
            mock.patch.object(
                jira_update.urllib.request, "urlopen", side_effect=responses
            ) as urlopen,
            self.assertRaisesRegex(ValueError, "当前不可用"),
        ):
            jira_update.apply_updates(
                self.config, "JIRA-1234", "comment", "999", "tester"
            )

        self.assertEqual(
            [call.args[0].get_method() for call in urlopen.call_args_list],
            ["GET", "GET"],
        )

    def test_confirmation_mismatch_stops_before_config_or_write(self):
        with mock.patch.object(jira_update, "load_config") as load_config:
            exit_code = jira_update.main(
                [
                    "apply",
                    "JIRA-1234",
                    "--comment-file",
                    "/not/read",
                    "--transition-id",
                    "81",
                    "--assignee",
                    "tester",
                    "--confirm",
                    "JIRA-9999",
                ]
            )

        self.assertEqual(exit_code, 1)
        load_config.assert_not_called()

    def test_partial_failure_reports_completed_step_without_retry(self):
        assignment_error = urllib.error.HTTPError(
            "https://jira.example.com/rest/api/2/issue/JIRA-1234/assignee",
            403,
            "Forbidden",
            {},
            io.BytesIO(b"forbidden"),
        )
        responses = [
            FakeResponse(ISSUE),
            FakeResponse(TRANSITIONS),
            FakeResponse(),
            FakeResponse(),
            assignment_error,
        ]
        with (
            mock.patch.object(
                jira_update.urllib.request, "urlopen", side_effect=responses
            ) as urlopen,
            self.assertRaises(jira_update.PartialUpdateError) as raised,
        ):
            jira_update.apply_updates(
                self.config, "JIRA-1234", "comment", "81", "tester"
            )

        self.assertEqual(
            raised.exception.completed, ["添加 comment", "执行 transition 81 -> TEST"]
        )
        self.assertIn("转派给 tester", raised.exception.failed_step)
        self.assertEqual(urlopen.call_count, 5)


if __name__ == "__main__":
    unittest.main()
