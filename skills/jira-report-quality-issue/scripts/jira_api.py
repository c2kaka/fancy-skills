#!/usr/bin/env python3
"""Small, guarded JIRA REST client for issue creation and screenshot upload."""

from __future__ import annotations

import base64
import http.client
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jira_draft import render_cloud_description, render_server_description

REQUIRED_SETTINGS = (
    "JIRA_BASE_URL",
    "JIRA_USER",
    "JIRA_PASSWORD",
    "JIRA_PROJECT_KEY",
    "JIRA_ISSUE_TYPE",
)
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


class JiraError(RuntimeError):
    """Base class for safe JIRA failures."""


class ConfigurationError(JiraError):
    """Raised before network access when local configuration is invalid."""


class ApiError(JiraError):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


class OutcomeUnknownError(JiraError):
    """Raised when a write may have reached JIRA but no response was received."""


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    user: str
    password: str
    project_key: str
    issue_type: str
    components: tuple[str, ...] = ()
    fix_versions: tuple[str, ...] = ()


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: dict[str, str]
    data: Any


@dataclass(frozen=True)
class Deployment:
    kind: str
    api_version: int
    raw_type: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        raise ConfigurationError(f"找不到配置文件：{path}")
    values: dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    raise ConfigurationError(f".env 第 {line_number} 行缺少 '='。")
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if value and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                values[key] = value
    except OSError as exc:
        raise ConfigurationError(f"无法读取配置文件：{path}: {exc}") from exc
    return values


def _json_string_list(values: dict[str, str], key: str) -> tuple[str, ...]:
    raw = values.get(key)
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"{key} 必须是 JSON 字符串数组。") from exc
    if not isinstance(parsed, list) or any(
        not isinstance(item, str) or not item.strip() for item in parsed
    ):
        raise ConfigurationError(f"{key} 必须是非空字符串组成的 JSON 数组。")
    return tuple(dict.fromkeys(item.strip() for item in parsed))


def load_config(env_path: Path) -> JiraConfig:
    values = load_env(env_path)
    missing = [key for key in REQUIRED_SETTINGS if not values.get(key)]
    if missing:
        raise ConfigurationError(f".env 缺少配置：{', '.join(missing)}")
    parsed = urllib.parse.urlsplit(values["JIRA_BASE_URL"].rstrip("/"))
    if parsed.scheme != "https" or not parsed.netloc:
        raise ConfigurationError("JIRA_BASE_URL 必须是有效的 HTTPS origin。")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError("JIRA_BASE_URL 不能包含凭据、query 或 fragment。")
    if parsed.path not in {"", "/"}:
        raise ConfigurationError("JIRA_BASE_URL 不能包含路径。")
    return JiraConfig(
        base_url=urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", "")),
        user=values["JIRA_USER"],
        password=values["JIRA_PASSWORD"],
        project_key=values["JIRA_PROJECT_KEY"],
        issue_type=values["JIRA_ISSUE_TYPE"],
        components=_json_string_list(values, "JIRA_COMPONENTS"),
        fix_versions=_json_string_list(values, "JIRA_FIX_VERSIONS"),
    )


def _safe_error_body(raw: bytes) -> str:
    if not raw:
        return "无响应内容"
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "JIRA 返回了非 JSON 错误响应"
    if isinstance(value, dict):
        messages: list[str] = []
        error_messages = value.get("errorMessages")
        if isinstance(error_messages, list):
            messages.extend(str(item) for item in error_messages)
        errors = value.get("errors")
        if isinstance(errors, dict):
            messages.extend(f"{key}: {item}" for key, item in errors.items())
        if messages:
            return "; ".join(messages)[:2000]
    return "JIRA 返回了结构化错误响应"


class JiraClient:
    def __init__(self, config: JiraConfig, *, timeout: float = 30.0):
        self.config = config
        self.timeout = timeout
        credentials = f"{config.user}:{config.password}".encode()
        self._authorization = "Basic " + base64.b64encode(credentials).decode("ascii")
        self._opener = urllib.request.build_opener(_NoRedirect())

    def _url(self, path: str, query: dict[str, str | int] | None = None) -> str:
        if not path.startswith("/"):
            raise ConfigurationError("JIRA API path 必须以 '/' 开头。")
        suffix = f"?{urllib.parse.urlencode(query)}" if query else ""
        return f"{self.config.base_url}{path}{suffix}"

    def request_json(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str | int] | None = None,
        body: object | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> HttpResult:
        data = (
            None
            if body is None
            else json.dumps(body, ensure_ascii=False).encode("utf-8")
        )
        headers = {"Accept": "application/json", "Authorization": self._authorization}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self._url(path, query), data=data, headers=headers, method=method
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ApiError(
                        "JIRA 响应超过安全读取上限。", status=response.status
                    )
                status = response.status
                response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
            if exc.code in {301, 302, 303, 307, 308}:
                raise ApiError(
                    "JIRA API 返回重定向；为防止凭据泄漏已拒绝跟随。", status=exc.code
                ) from exc
            message = _safe_error_body(raw)
            if exc.code == 401:
                message = "JIRA 认证失败（401）。"
            elif exc.code == 403:
                message = "JIRA 权限不足（403）。"
            elif exc.code == 404:
                message = "JIRA 资源不存在（404）。"
            raise ApiError(message, status=exc.code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                raise OutcomeUnknownError(
                    f"JIRA 写请求没有得到明确响应：{type(exc).__name__}"
                ) from exc
            raise ApiError(f"JIRA 只读请求失败：{type(exc).__name__}") from exc
        if status not in expected:
            raise ApiError(f"JIRA 返回未预期状态码 {status}。", status=status)
        if not raw:
            parsed: object = None
        else:
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ApiError("JIRA 返回了无效 JSON。", status=status) from exc
        return HttpResult(status=status, headers=response_headers, data=parsed)

    def detect_deployment(self) -> Deployment:
        result = self.request_json("GET", "/rest/api/2/serverInfo")
        if not isinstance(result.data, dict):
            raise ApiError("serverInfo 响应格式无效。")
        raw_type = str(result.data.get("deploymentType") or "").strip()
        normalized = raw_type.casefold().replace(" ", "")
        if normalized == "cloud":
            return Deployment(kind="cloud", api_version=3, raw_type=raw_type)
        if normalized in {"server", "datacenter"}:
            return Deployment(kind="server", api_version=2, raw_type=raw_type)
        raise ApiError(f"无法识别 JIRA deploymentType：{raw_type or 'missing'}")

    def current_user(self, deployment: Deployment) -> dict[str, object]:
        result = self.request_json("GET", f"/rest/api/{deployment.api_version}/myself")
        if not isinstance(result.data, dict):
            raise ApiError("myself 响应格式无效。")
        identity_field = "accountId" if deployment.kind == "cloud" else "name"
        if not result.data.get(identity_field):
            raise ApiError(f"myself 缺少 {identity_field}，不能证明账户所有者身份。")
        return result.data

    def permissions(
        self, deployment: Deployment, project_key: str
    ) -> dict[str, object]:
        names = "BROWSE_PROJECTS,CREATE_ISSUES,ASSIGN_ISSUES,ASSIGNABLE_USER,CREATE_ATTACHMENTS"
        result = self.request_json(
            "GET",
            f"/rest/api/{deployment.api_version}/mypermissions",
            query={"projectKey": project_key, "permissions": names},
        )
        if not isinstance(result.data, dict):
            raise ApiError("mypermissions 响应格式无效。")
        return result.data

    def attachment_meta(self, deployment: Deployment) -> dict[str, object]:
        result = self.request_json(
            "GET", f"/rest/api/{deployment.api_version}/attachment/meta"
        )
        if not isinstance(result.data, dict):
            raise ApiError("attachment meta 响应格式无效。")
        return result.data

    def create_metadata(
        self, deployment: Deployment, project_key: str, issue_type_name: str
    ) -> dict[str, object]:
        if deployment.kind == "server":
            result = self.request_json(
                "GET",
                "/rest/api/2/issue/createmeta",
                query={
                    "projectKeys": project_key,
                    "issuetypeNames": issue_type_name,
                    "expand": "projects.issuetypes.fields",
                },
            )
            return _server_create_metadata(result.data, project_key, issue_type_name)

        issue_types = self.request_json(
            "GET",
            f"/rest/api/3/issue/createmeta/{urllib.parse.quote(project_key, safe='')}/issuetypes",
        ).data
        issue_type = _find_cloud_issue_type(issue_types, issue_type_name)
        issue_type_id = str(issue_type.get("id") or "")
        if not issue_type_id:
            raise ApiError("Cloud create metadata 缺少 issue type id。")
        fields = self.request_json(
            "GET",
            f"/rest/api/3/issue/createmeta/{urllib.parse.quote(project_key, safe='')}/issuetypes/"
            f"{urllib.parse.quote(issue_type_id, safe='')}",
        ).data
        return {
            "projectKey": project_key,
            "issueType": issue_type,
            "fields": _normalize_cloud_fields(fields),
        }

    def search_candidates(
        self, deployment: Deployment, project_key: str, issue_type_name: str
    ) -> list[dict[str, object]]:
        quoted_project = _jql_string(project_key)
        quoted_type = _jql_string(issue_type_name)
        jql = (
            f"project = {quoted_project} AND issuetype = {quoted_type} "
            "AND statusCategory != Done ORDER BY updated DESC"
        )
        path = (
            "/rest/api/3/search/jql"
            if deployment.kind == "cloud"
            else "/rest/api/2/search"
        )
        result = self.request_json(
            "GET",
            path,
            query={
                "jql": jql,
                "fields": "summary,status,description,labels,components,updated",
                "maxResults": 50,
            },
        )
        if not isinstance(result.data, dict) or not isinstance(
            result.data.get("issues"), list
        ):
            raise ApiError("JIRA search 响应格式无效。")
        return [
            _candidate_summary(item)
            for item in result.data["issues"]
            if isinstance(item, dict)
        ]

    def search_fingerprint(
        self, deployment: Deployment, project_key: str, issue_fingerprint: str
    ) -> list[dict[str, object]]:
        marker = f"Creation fingerprint: {issue_fingerprint}"
        jql = f"project = {_jql_string(project_key)} AND text ~ {_jql_string(marker)} ORDER BY created DESC"
        path = (
            "/rest/api/3/search/jql"
            if deployment.kind == "cloud"
            else "/rest/api/2/search"
        )
        result = self.request_json(
            "GET",
            path,
            query={
                "jql": jql,
                "fields": "summary,status,description,attachment",
                "maxResults": 20,
            },
        )
        if not isinstance(result.data, dict) or not isinstance(
            result.data.get("issues"), list
        ):
            raise ApiError("fingerprint search 响应格式无效。")
        matches: list[dict[str, object]] = []
        for item in result.data["issues"]:
            if isinstance(item, dict) and marker in json.dumps(
                item.get("fields", {}).get("description"), ensure_ascii=False
            ):
                matches.append(item)
        return matches

    def create_issue(
        self,
        deployment: Deployment,
        issue: dict[str, object],
        current_user: dict[str, object],
        metadata: dict[str, object],
    ) -> HttpResult:
        fields = build_create_fields(deployment, issue, current_user, metadata)
        return self.request_json(
            "POST",
            f"/rest/api/{deployment.api_version}/issue",
            body={"fields": fields},
            expected=(201,),
        )

    def get_issue(
        self,
        deployment: Deployment,
        issue_key: str,
        *,
        extra_fields: tuple[str, ...] = (),
    ) -> dict[str, object]:
        fields = (
            "project",
            "issuetype",
            "summary",
            "description",
            "reporter",
            "assignee",
            "priority",
            "components",
            "environment",
            "fixVersions",
            "labels",
            "attachment",
            *extra_fields,
        )
        result = self.request_json(
            "GET",
            f"/rest/api/{deployment.api_version}/issue/{urllib.parse.quote(issue_key, safe='')}",
            query={"fields": ",".join(dict.fromkeys(fields))},
        )
        if not isinstance(result.data, dict):
            raise ApiError("issue GET 响应格式无效。")
        return result.data

    def upload_attachment(
        self,
        deployment: Deployment,
        issue_key: str,
        file_path: Path,
        upload_name: str,
        mime_type: str,
    ) -> HttpResult:
        if not upload_name or any(
            not (
                character.isascii()
                and (character.isalnum() or character in {"-", "_", "."})
            )
            for character in upload_name
        ):
            raise ConfigurationError(
                "附件上传名只能包含 ASCII 字母、数字、连字符、下划线和点。"
            )
        if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise ConfigurationError(f"不支持的附件 MIME type：{mime_type}")
        boundary = f"codex-jira-{uuid.uuid4().hex}"
        preamble = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{upload_name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("ascii")
        ending = f"\r\n--{boundary}--\r\n".encode("ascii")
        file_size = file_path.stat().st_size
        parsed = urllib.parse.urlsplit(self.config.base_url)
        connection = http.client.HTTPSConnection(
            parsed.hostname,
            parsed.port or 443,
            timeout=self.timeout,
            context=ssl.create_default_context(),
        )
        path = f"/rest/api/{deployment.api_version}/issue/{urllib.parse.quote(issue_key, safe='')}/attachments"
        try:
            connection.putrequest("POST", path)
            connection.putheader("Accept", "application/json")
            connection.putheader("Authorization", self._authorization)
            connection.putheader("X-Atlassian-Token", "no-check")
            connection.putheader(
                "Content-Type", f"multipart/form-data; boundary={boundary}"
            )
            connection.putheader(
                "Content-Length", str(len(preamble) + file_size + len(ending))
            )
            connection.endheaders()
            connection.send(preamble)
            with file_path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    connection.send(chunk)
            connection.send(ending)
            response = connection.getresponse()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ApiError("附件响应超过安全读取上限。", status=response.status)
            if response.status != 200:
                raise ApiError(_safe_error_body(raw), status=response.status)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ApiError(
                    "附件 API 返回无效 JSON。", status=response.status
                ) from exc
            return HttpResult(
                status=response.status, headers=dict(response.getheaders()), data=data
            )
        except ApiError:
            raise
        except (OSError, http.client.HTTPException, TimeoutError) as exc:
            raise OutcomeUnknownError(
                f"附件上传没有得到明确响应：{type(exc).__name__}"
            ) from exc
        finally:
            connection.close()


def _jql_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _candidate_summary(issue: dict[str, object]) -> dict[str, object]:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    status = fields.get("status") if isinstance(fields.get("status"), dict) else {}
    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": status.get("name"),
        "updated": fields.get("updated"),
        "labels": fields.get("labels") or [],
        "components": fields.get("components") or [],
        "description": fields.get("description"),
    }


def _server_create_metadata(
    data: object, project_key: str, issue_type_name: str
) -> dict[str, object]:
    if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
        raise ApiError("Server create metadata 响应格式无效。")
    project = next(
        (
            item
            for item in data["projects"]
            if isinstance(item, dict) and item.get("key") == project_key
        ),
        None,
    )
    if not isinstance(project, dict):
        raise ApiError(f"项目不存在或当前账户不能创建：{project_key}")
    issue_types = project.get("issuetypes")
    if not isinstance(issue_types, list):
        raise ApiError("Server create metadata 缺少 issue types。")
    issue_type = next(
        (
            item
            for item in issue_types
            if isinstance(item, dict) and item.get("name") == issue_type_name
        ),
        None,
    )
    if not isinstance(issue_type, dict):
        raise ApiError(f"项目 {project_key} 不允许创建 issue type：{issue_type_name}")
    fields = issue_type.get("fields")
    if not isinstance(fields, dict):
        raise ApiError("Server create metadata 缺少 fields。")
    return {"projectKey": project_key, "issueType": issue_type, "fields": fields}


def _find_cloud_issue_type(data: object, issue_type_name: str) -> dict[str, object]:
    if isinstance(data, dict):
        values = data.get("values") or data.get("issueTypes")
    else:
        values = data
    if not isinstance(values, list):
        raise ApiError("Cloud issue type metadata 响应格式无效。")
    issue_type = next(
        (
            item
            for item in values
            if isinstance(item, dict) and item.get("name") == issue_type_name
        ),
        None,
    )
    if not isinstance(issue_type, dict):
        raise ApiError(f"Cloud 项目不允许创建 issue type：{issue_type_name}")
    return issue_type


def _normalize_cloud_fields(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        raise ApiError("Cloud field metadata 响应格式无效。")
    raw_fields = data.get("fields") or data.get("values")
    if isinstance(raw_fields, dict):
        return raw_fields
    if not isinstance(raw_fields, list):
        raise ApiError("Cloud field metadata 缺少 fields/values。")
    fields: dict[str, object] = {}
    for field in raw_fields:
        if not isinstance(field, dict):
            continue
        field_id = field.get("fieldId") or field.get("key") or field.get("id")
        if field_id:
            fields[str(field_id)] = field
    return fields


def _allowed_names(field: object) -> set[str]:
    if not isinstance(field, dict) or not isinstance(field.get("allowedValues"), list):
        return set()
    names: set[str] = set()
    for item in field["allowedValues"]:
        if isinstance(item, dict):
            value = item.get("name") or item.get("value")
            if value:
                names.add(str(value))
    return names


def _allowed_identities(field: object) -> set[str]:
    if not isinstance(field, dict) or not isinstance(field.get("allowedValues"), list):
        return set()
    identities: set[str] = set()
    for item in field["allowedValues"]:
        if not isinstance(item, dict):
            continue
        for key in ("accountId", "name", "key"):
            if item.get(key):
                identities.add(str(item[key]))
    return identities


def build_create_fields(
    deployment: Deployment,
    issue: dict[str, object],
    current_user: dict[str, object],
    metadata: dict[str, object],
) -> dict[str, object]:
    fields_meta = metadata.get("fields")
    if not isinstance(fields_meta, dict):
        raise ApiError("create metadata fields 格式无效。")
    fields: dict[str, object] = {
        "project": {"key": issue["projectKey"]},
        "issuetype": {"name": issue["issueType"]},
        "summary": issue["summary"],
        "description": render_cloud_description(issue)
        if deployment.kind == "cloud"
        else render_server_description(issue),
        "assignee": {"accountId": current_user["accountId"]}
        if deployment.kind == "cloud"
        else {"name": current_user["name"]},
    }
    identity_key = "accountId" if deployment.kind == "cloud" else "name"
    allowed_assignees = _allowed_identities(fields_meta.get("assignee"))
    if allowed_assignees and str(current_user[identity_key]) not in allowed_assignees:
        raise ApiError("当前认证账户不在 create metadata 的可分配用户中。")
    if issue.get("priority"):
        allowed = _allowed_names(fields_meta.get("priority"))
        if allowed and issue["priority"] not in allowed:
            raise ApiError(f"priority 不在项目允许值中：{issue['priority']}")
        fields["priority"] = {"name": issue["priority"]}
    if issue.get("components"):
        allowed = _allowed_names(fields_meta.get("components"))
        unknown = set(issue["components"]) - allowed if allowed else set()
        if unknown:
            raise ApiError(f"component 不在项目允许值中：{', '.join(sorted(unknown))}")
        fields["components"] = [{"name": name} for name in issue["components"]]
    if issue.get("environment"):
        if "environment" not in fields_meta:
            raise ApiError("environment 不在项目 create metadata 中。")
        fields["environment"] = issue["environment"]
    if issue.get("fixVersions"):
        if "fixVersions" not in fields_meta:
            raise ApiError("fixVersions 不在项目 create metadata 中。")
        allowed = _allowed_names(fields_meta.get("fixVersions"))
        unknown = set(issue["fixVersions"]) - allowed if allowed else set()
        if unknown:
            raise ApiError(f"fixVersion 不在项目允许值中：{', '.join(sorted(unknown))}")
        fields["fixVersions"] = [{"name": name} for name in issue["fixVersions"]]
    if issue.get("labels"):
        fields["labels"] = issue["labels"]
    custom_fields = issue.get("customFields")
    if isinstance(custom_fields, dict):
        for key, value in custom_fields.items():
            if key not in fields_meta:
                raise ApiError(f"custom field 不在 create metadata 中：{key}")
            fields[key] = value

    missing_required: list[str] = []
    for key, field_meta in fields_meta.items():
        if not isinstance(field_meta, dict) or field_meta.get("required") is not True:
            continue
        if key not in fields:
            missing_required.append(str(field_meta.get("name") or key))
    if missing_required:
        raise ApiError(f"缺少 JIRA 必填字段：{', '.join(sorted(missing_required))}")
    return fields


def denied_permissions(data: dict[str, object]) -> tuple[list[str], list[str]]:
    permissions = data.get("permissions")
    if not isinstance(permissions, dict):
        raise ApiError("mypermissions 缺少 permissions。")
    required = (
        "BROWSE_PROJECTS",
        "CREATE_ISSUES",
        "ASSIGN_ISSUES",
        "ASSIGNABLE_USER",
        "CREATE_ATTACHMENTS",
    )
    denied: list[str] = []
    unknown: list[str] = []
    for permission in required:
        value = permissions.get(permission)
        if not isinstance(value, dict) or "havePermission" not in value:
            unknown.append(permission)
        elif value.get("havePermission") is not True:
            denied.append(permission)
    return denied, unknown
