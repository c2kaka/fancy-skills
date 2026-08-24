from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from jira_api import (
    ApiError,
    ConfigurationError,
    Deployment,
    JiraClient,
    JiraConfig,
    build_create_fields,
    denied_permissions,
    load_config,
)


class _Response:
    status = 200

    def read(self, _size: int) -> bytes:
        return json.dumps(
            [{"id": "10001", "filename": "01-proof-deadbeef.png"}]
        ).encode()

    def getheaders(self) -> list[tuple[str, str]]:
        return [("Content-Type", "application/json")]


class _Connection:
    instances: ClassVar[list[_Connection]] = []

    def __init__(self, *_args, **_kwargs) -> None:
        self.headers: dict[str, str] = {}
        self.sent = bytearray()
        self.__class__.instances.append(self)

    def putrequest(self, method: str, path: str) -> None:
        self.method = method
        self.path = path

    def putheader(self, key: str, value: str) -> None:
        self.headers[key] = value

    def endheaders(self) -> None:
        pass

    def send(self, data: bytes) -> None:
        self.sent.extend(data)

    def getresponse(self) -> _Response:
        return _Response()

    def close(self) -> None:
        pass


class ApiTests(unittest.TestCase):
    def test_config_requires_https_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "JIRA_BASE_URL=http://jira.example.com/path\nJIRA_USER=me\nJIRA_PASSWORD=secret\n"
                "JIRA_PROJECT_KEY=TEST\nJIRA_ISSUE_TYPE=Bug\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigurationError, "HTTPS"):
                load_config(path)

    def test_config_loads_component_and_fix_version_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "JIRA_BASE_URL=https://jira.example.com\nJIRA_USER=me\n"
                "JIRA_PASSWORD=secret\nJIRA_PROJECT_KEY=TEST\nJIRA_ISSUE_TYPE=Bug\n"
                'JIRA_COMPONENTS=["Frontend", "Platform", "Frontend"]\n'
                'JIRA_FIX_VERSIONS=["Future"]\n',
                encoding="utf-8",
            )
            config = load_config(path)

        self.assertEqual(config.components, ("Frontend", "Platform"))
        self.assertEqual(config.fix_versions, ("Future",))

    def test_config_rejects_non_array_component_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "JIRA_BASE_URL=https://jira.example.com\nJIRA_USER=me\n"
                "JIRA_PASSWORD=secret\nJIRA_PROJECT_KEY=TEST\nJIRA_ISSUE_TYPE=Bug\n"
                "JIRA_COMPONENTS=Frontend\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigurationError, "JSON 字符串数组"):
                load_config(path)

    def test_build_server_fields_assigns_authenticated_owner(self) -> None:
        deployment = Deployment(kind="server", api_version=2, raw_type="Server")
        issue = {
            "projectKey": "TEST",
            "issueType": "Bug",
            "summary": "Save fails",
            "description": {
                "background": "Background",
                "actualBehavior": "Actual",
                "expectedBehavior": "Expected",
                "impact": "Impact",
                "reproductionSteps": ["Step"],
                "evidence": ["Evidence"],
                "affectedScope": ["Scope"],
                "verification": ["Verification"],
                "limitations": [],
                "suggestedDirection": "Direction",
            },
            "issueFingerprint": "a" * 64,
            "screenshots": [],
            "priority": "High",
            "components": ["Frontend"],
            "environment": "Test environment",
            "fixVersions": ["Future"],
            "labels": ["quality"],
            "customFields": {"customfield_10000": "value"},
        }
        metadata = {
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
                "customfield_10000": {"required": True},
            }
        }
        fields = build_create_fields(deployment, issue, {"name": "owner"}, metadata)

        self.assertEqual(fields["assignee"], {"name": "owner"})
        self.assertEqual(fields["environment"], "Test environment")
        self.assertEqual(fields["fixVersions"], [{"name": "Future"}])
        self.assertEqual(fields["customfield_10000"], "value")
        self.assertIn("Creation fingerprint", fields["description"])

        issue["fixVersions"] = ["Unknown"]
        with self.assertRaisesRegex(ApiError, "fixVersion 不在项目允许值中"):
            build_create_fields(deployment, issue, {"name": "owner"}, metadata)

    def test_create_fields_reject_owner_outside_allowed_assignees(self) -> None:
        deployment = Deployment(kind="cloud", api_version=3, raw_type="Cloud")
        issue = {
            "projectKey": "TEST",
            "issueType": "Bug",
            "summary": "Save fails",
            "description": {
                "background": "Background",
                "actualBehavior": "Actual",
                "expectedBehavior": "Expected",
                "impact": "Impact",
                "reproductionSteps": ["Step"],
                "evidence": ["Evidence"],
                "affectedScope": ["Scope"],
                "verification": ["Verification"],
                "limitations": [],
                "suggestedDirection": "Direction",
            },
            "issueFingerprint": "a" * 64,
            "screenshots": [],
            "priority": None,
            "components": [],
            "environment": None,
            "fixVersions": [],
            "labels": [],
            "customFields": {},
        }
        metadata = {
            "fields": {
                "project": {"required": True},
                "issuetype": {"required": True},
                "summary": {"required": True},
                "description": {"required": True},
                "assignee": {
                    "required": True,
                    "allowedValues": [{"accountId": "someone-else"}],
                },
            }
        }
        with self.assertRaisesRegex(ApiError, "可分配用户"):
            build_create_fields(
                deployment, issue, {"accountId": "owner-account"}, metadata
            )

    def test_permission_result_separates_denied_and_unknown(self) -> None:
        denied, unknown = denied_permissions(
            {
                "permissions": {
                    "BROWSE_PROJECTS": {"havePermission": True},
                    "CREATE_ISSUES": {"havePermission": False},
                }
            }
        )
        self.assertEqual(denied, ["CREATE_ISSUES"])
        self.assertIn("CREATE_ATTACHMENTS", unknown)

    def test_multipart_streams_file_with_required_headers(self) -> None:
        _Connection.instances.clear()
        config = JiraConfig(
            "https://jira.example.com", "owner", "secret", "TEST", "Bug"
        )
        client = JiraClient(config)
        deployment = Deployment(kind="server", api_version=2, raw_type="Server")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.png"
            path.write_bytes(b"image-bytes")
            with patch("jira_api.http.client.HTTPSConnection", _Connection):
                result = client.upload_attachment(
                    deployment, "TEST-1", path, "01-proof-deadbeef.png", "image/png"
                )

        connection = _Connection.instances[0]
        self.assertEqual(result.status, 200)
        self.assertEqual(connection.method, "POST")
        self.assertEqual(connection.path, "/rest/api/2/issue/TEST-1/attachments")
        self.assertEqual(connection.headers["X-Atlassian-Token"], "no-check")
        self.assertIn("multipart/form-data", connection.headers["Content-Type"])
        self.assertIn(b'name="file"', connection.sent)
        self.assertIn(b"image-bytes", connection.sent)

    def test_multipart_rejects_header_injection_filename(self) -> None:
        config = JiraConfig(
            "https://jira.example.com", "owner", "secret", "TEST", "Bug"
        )
        client = JiraClient(config)
        deployment = Deployment(kind="server", api_version=2, raw_type="Server")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.png"
            path.write_bytes(b"image-bytes")
            with self.assertRaisesRegex(ConfigurationError, "上传名"):
                client.upload_attachment(
                    deployment,
                    "TEST-1",
                    path,
                    'proof"\r\nX-Evil: yes.png',
                    "image/png",
                )


if __name__ == "__main__":
    unittest.main()
