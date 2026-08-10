from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "jira_update.py"
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


TODO_ISSUE = {
    "fields": {
        "status": {"id": "1", "name": "待办"},
        "reporter": {"name": "tester", "displayName": "Test User"},
        "assignee": {"name": "developer", "displayName": "Dev User"},
    }
}
START_TRANSITIONS = {
    "transitions": [
        {
            "id": "11",
            "name": "Start Process",
            "to": {"id": "3", "name": "In Progress"},
        }
    ]
}
TEST_TRANSITIONS = {
    "transitions": [
        {
            "id": "21",
            "name": "Start preview",
            "to": {"id": "4", "name": "PREVIEW"},
        }
    ]
}
FINAL_TRANSITIONS = {
    "transitions": [
        {
            "id": "31",
            "name": "Start test",
            "to": {"id": "10002", "name": "TEST"},
        }
    ]
}
FINAL_ISSUE = {
    "fields": {
        "status": {"id": "10002", "name": "TEST"},
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

    def test_start_process_runs_confirmed_path_to_test_then_assigns_tester(self):
        responses = [
            FakeResponse(TODO_ISSUE),
            FakeResponse(START_TRANSITIONS),
            FakeResponse(),
            FakeResponse(),
            FakeResponse(TEST_TRANSITIONS),
            FakeResponse(),
            FakeResponse(FINAL_TRANSITIONS),
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
                "修复结果",
                "11",
                "tester",
                "TEST",
                ["Start preview", "Start test"],
            )

        requests = [call.args[0] for call in urlopen.call_args_list]
        self.assertEqual(
            [request.get_method() for request in requests],
            [
                "GET",
                "GET",
                "POST",
                "POST",
                "GET",
                "POST",
                "GET",
                "POST",
                "PUT",
                "GET",
            ],
        )
        self.assertEqual(
            json.loads(requests[3].data.decode("utf-8")),
            {"transition": {"id": "11"}},
        )
        self.assertEqual(
            json.loads(requests[5].data.decode("utf-8")),
            {"transition": {"id": "21"}},
        )
        self.assertEqual(
            json.loads(requests[7].data.decode("utf-8")),
            {"transition": {"id": "31"}},
        )
        self.assertEqual(
            json.loads(requests[8].data.decode("utf-8")), {"name": "tester"}
        )
        self.assertEqual(
            [step["id"] for step in result["transition_path"]],
            ["11", "21", "31"],
        )
        self.assertEqual(result["status"], "TEST")
        self.assertEqual(result["assignee"], "tester")

    def test_missing_expected_transition_stops_before_assignment_without_retry(self):
        unrelated_transitions = {
            "transitions": [
                {
                    "id": "41",
                    "name": "Resolve",
                    "to": {"id": "6", "name": "Done"},
                }
            ]
        }
        responses = [
            FakeResponse(TODO_ISSUE),
            FakeResponse(START_TRANSITIONS),
            FakeResponse(),
            FakeResponse(),
            FakeResponse(unrelated_transitions),
        ]
        with (
            mock.patch.object(
                jira_update.urllib.request, "urlopen", side_effect=responses
            ) as urlopen,
            self.assertRaises(jira_update.PartialUpdateError) as raised,
        ):
            jira_update.apply_updates(
                self.config,
                "JIRA-1234",
                "修复结果",
                "11",
                "tester",
                "TEST",
                ["Start preview", "Start test"],
            )

        self.assertEqual(
            raised.exception.completed,
            ["添加 comment", "执行 transition 11 -> In Progress"],
        )
        self.assertIn("transition name 'Start preview'", raised.exception.failed_step)
        self.assertEqual(urlopen.call_count, 5)

    def test_single_transition_mode_remains_supported(self):
        in_progress_issue = {
            **TODO_ISSUE,
            "fields": {
                **TODO_ISSUE["fields"],
                "status": {"id": "3", "name": "In Progress"},
            },
        }
        responses = [
            FakeResponse(in_progress_issue),
            FakeResponse(FINAL_TRANSITIONS),
            FakeResponse(),
            FakeResponse(),
            FakeResponse(),
            FakeResponse(FINAL_ISSUE),
        ]
        with mock.patch.object(
            jira_update.urllib.request, "urlopen", side_effect=responses
        ) as urlopen:
            result = jira_update.apply_updates(
                self.config, "JIRA-1234", "修复结果", "31", "tester"
            )

        self.assertEqual(
            [call.args[0].get_method() for call in urlopen.call_args_list],
            ["GET", "GET", "POST", "POST", "PUT", "GET"],
        )
        self.assertEqual(result["status"], "TEST")

    def test_resume_after_partial_skips_existing_comment(self):
        reviewed_issue = {
            **TODO_ISSUE,
            "fields": {
                **TODO_ISSUE["fields"],
                "status": {"id": "10001", "name": "Reviewed"},
            },
        }
        start_test_transitions = {
            "transitions": [
                {
                    "id": "31",
                    "name": "Start Test",
                    "to": {"id": "10002", "name": "TEST"},
                }
            ]
        }
        responses = [
            FakeResponse(reviewed_issue),
            FakeResponse(start_test_transitions),
            FakeResponse(),
            FakeResponse(),
            FakeResponse(FINAL_ISSUE),
        ]
        with mock.patch.object(
            jira_update.urllib.request, "urlopen", side_effect=responses
        ) as urlopen:
            result = jira_update.apply_updates(
                self.config, "JIRA-1234", None, "31", "tester", "TEST"
            )

        requests = [call.args[0] for call in urlopen.call_args_list]
        self.assertEqual(
            [request.get_method() for request in requests],
            ["GET", "GET", "POST", "PUT", "GET"],
        )
        self.assertEqual(
            json.loads(requests[2].data.decode("utf-8")),
            {"transition": {"id": "31"}},
        )
        self.assertEqual(result["comment"], "skipped_existing")
        self.assertEqual(result["status"], "TEST")
        self.assertEqual(result["assignee"], "tester")

    def test_resume_cli_passes_no_comment_to_guarded_update(self):
        expected = {
            "issue_key": "JIRA-1234",
            "comment": "skipped_existing",
            "assignee": "tester",
            "transition_id": "31",
            "transition_button": "Start Test",
            "transition_path": [],
            "status": "TEST",
        }
        with (
            mock.patch.object(jira_update, "load_config", return_value=self.config),
            mock.patch.object(
                jira_update, "apply_updates", return_value=expected
            ) as apply_updates,
        ):
            exit_code = jira_update.main(
                [
                    "resume",
                    "JIRA-1234",
                    "--transition-id",
                    "31",
                    "--target-status",
                    "TEST",
                    "--assignee",
                    "tester",
                    "--confirm",
                    "JIRA-1234",
                ]
            )

        self.assertEqual(exit_code, 0)
        apply_updates.assert_called_once_with(
            self.config,
            "JIRA-1234",
            None,
            "31",
            "tester",
            "TEST",
            [],
        )

    def test_resume_partial_failure_does_not_repeat_comment_or_assign(self):
        in_progress_issue = {
            **TODO_ISSUE,
            "fields": {
                **TODO_ISSUE["fields"],
                "status": {"id": "3", "name": "In Progress"},
            },
        }
        start_review_transitions = {
            "transitions": [
                {
                    "id": "21",
                    "name": "Start Review",
                    "to": {"id": "10001", "name": "Reviewed"},
                }
            ]
        }
        unexpected_transitions = {
            "transitions": [
                {
                    "id": "41",
                    "name": "Return",
                    "to": {"id": "3", "name": "In Progress"},
                }
            ]
        }
        responses = [
            FakeResponse(in_progress_issue),
            FakeResponse(start_review_transitions),
            FakeResponse(),
            FakeResponse(unexpected_transitions),
        ]
        with (
            mock.patch.object(
                jira_update.urllib.request, "urlopen", side_effect=responses
            ) as urlopen,
            self.assertRaises(jira_update.PartialUpdateError) as raised,
        ):
            jira_update.apply_updates(
                self.config,
                "JIRA-1234",
                None,
                "21",
                "tester",
                "TEST",
                ["Start Test"],
            )

        self.assertEqual(
            raised.exception.completed,
            ["执行 transition 21 -> Reviewed"],
        )
        self.assertIn("transition name 'Start Test'", raised.exception.failed_step)
        self.assertEqual(
            [call.args[0].get_method() for call in urlopen.call_args_list],
            ["GET", "GET", "POST", "GET"],
        )

    def test_unknown_initial_transition_fails_before_any_write(self):
        responses = [FakeResponse(TODO_ISSUE), FakeResponse(START_TRANSITIONS)]
        with (
            mock.patch.object(
                jira_update.urllib.request, "urlopen", side_effect=responses
            ) as urlopen,
            self.assertRaisesRegex(ValueError, "当前不可用"),
        ):
            jira_update.apply_updates(
                self.config, "JIRA-1234", "修复结果", "999", "tester", "TEST"
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
                    "11",
                    "--target-status",
                    "TEST",
                    "--next-transition-name",
                    "Start preview",
                    "--next-transition-name",
                    "Start test",
                    "--assignee",
                    "tester",
                    "--confirm",
                    "JIRA-9999",
                ]
            )

        self.assertEqual(exit_code, 1)
        load_config.assert_not_called()

    def test_assignment_failure_after_transitions_is_partial_and_not_retried(self):
        assignment_error = urllib.error.HTTPError(
            "https://jira.example.com/rest/api/2/issue/JIRA-1234/assignee",
            403,
            "Forbidden",
            {},
            io.BytesIO(b"forbidden"),
        )
        responses = [
            FakeResponse(TODO_ISSUE),
            FakeResponse(START_TRANSITIONS),
            FakeResponse(),
            FakeResponse(),
            FakeResponse(TEST_TRANSITIONS),
            FakeResponse(),
            FakeResponse(FINAL_TRANSITIONS),
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
                self.config,
                "JIRA-1234",
                "修复结果",
                "11",
                "tester",
                "TEST",
                ["Start preview", "Start test"],
            )

        self.assertEqual(
            raised.exception.completed,
            [
                "添加 comment",
                "执行 transition 11 -> In Progress",
                "执行 transition 21 -> PREVIEW",
                "执行 transition 31 -> TEST",
            ],
        )
        self.assertIn("转派给 tester", raised.exception.failed_step)
        self.assertEqual(urlopen.call_count, 9)


if __name__ == "__main__":
    unittest.main()
