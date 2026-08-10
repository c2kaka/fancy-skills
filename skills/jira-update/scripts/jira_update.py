#!/usr/bin/env python3
"""Inspect and guardedly update one JIRA issue using a skill-local .env file."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SKILL_DIR / ".env"
REQUIRED_SETTINGS = ("JIRA_BASE_URL", "JIRA_USER", "JIRA_PASSWORD")
REQUEST_TIMEOUT_SECONDS = 30


class ConfigurationError(ValueError):
    """Raised when the skill-local configuration is missing or invalid."""


class JiraRequestError(RuntimeError):
    """Raised when a JIRA request fails."""


class PartialUpdateError(RuntimeError):
    """Raised after one or more writes succeeded and a later step failed."""

    def __init__(self, completed: list[str], failed_step: str, cause: Exception):
        self.completed = completed
        self.failed_step = failed_step
        self.cause = cause
        super().__init__(
            f"JIRA 更新部分完成。已完成：{', '.join(completed)}；"
            f"失败步骤：{failed_step}；原因：{cause}"
        )


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    user: str
    password: str


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE entries without shell evaluation or interpolation."""
    if not path.is_file():
        raise ConfigurationError(
            f"未找到配置文件：{path}。请复制 .env.example 为 .env 后填写配置。"
        )

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigurationError(f"无法读取配置文件 {path}：{exc}") from exc

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            raise ConfigurationError(f"{path} 第 {line_number} 行不是 KEY=VALUE 格式。")

        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if not key:
            raise ConfigurationError(f"{path} 第 {line_number} 行缺少配置名。")
        if value.startswith(("'", '"')):
            quote = value[0]
            if len(value) < 2 or not value.endswith(quote):
                raise ConfigurationError(f"{path} 第 {line_number} 行的引号不匹配。")
            value = value[1:-1]
        values[key] = value

    return values


def load_config(path: Path = ENV_FILE) -> JiraConfig:
    values = parse_env_file(path)
    missing = [key for key in REQUIRED_SETTINGS if not values.get(key)]
    if missing:
        raise ConfigurationError(
            f"配置文件 {path} 缺少非空配置：{', '.join(missing)}。"
        )

    base_url = values["JIRA_BASE_URL"].rstrip("/")
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ConfigurationError("JIRA_BASE_URL 必须是有效的 HTTPS 地址。")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError("JIRA_BASE_URL 不能包含凭证、查询参数或 URL 片段。")
    if parsed.path not in ("", "/"):
        raise ConfigurationError("JIRA_BASE_URL 不能包含路径。")

    return JiraConfig(
        base_url=base_url,
        user=values["JIRA_USER"],
        password=values["JIRA_PASSWORD"],
    )


def authorization_value(config: JiraConfig) -> str:
    token = base64.b64encode(f"{config.user}:{config.password}".encode()).decode()
    return f"Basic {token}"


def request_json(
    config: JiraConfig,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    url = config.base_url + path
    data = (
        json.dumps(body, ensure_ascii=False).encode("utf-8")
        if body is not None
        else None
    )
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", authorization_value(config))
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")

    try:
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            message = "认证失败（401）：请检查 .env 中的 JIRA_USER 和 JIRA_PASSWORD。"
        elif exc.code == 403:
            message = f"权限不足（403）：无权执行 {method} {path}。"
        elif exc.code == 404:
            message = f"未找到（404）：资源不存在或当前账号无权访问 {path}。"
        else:
            response_body = exc.read().decode(errors="replace")
            message = f"JIRA 请求失败，HTTP {exc.code}: {response_body[:500]}"
        raise JiraRequestError(message) from exc
    except urllib.error.URLError as exc:
        raise JiraRequestError(
            f"网络错误：无法连接 JIRA（{exc.reason}）。请检查 .env、VPN 和网络。"
        ) from exc

    if not raw.strip():
        return None
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JiraRequestError("JIRA 返回了无法解析的 JSON 响应。") from exc
    if not isinstance(parsed, dict):
        raise JiraRequestError("JIRA 返回的 JSON 不是对象。")
    return parsed


def encoded_issue_path(issue_key: str) -> str:
    key = issue_key.strip()
    if not key:
        raise ValueError("issue key 不能为空。")
    return urllib.parse.quote(key, safe="")


def get_issue(config: JiraConfig, issue_key: str) -> dict[str, Any]:
    key = encoded_issue_path(issue_key)
    data = request_json(
        config,
        "GET",
        f"/rest/api/2/issue/{key}?fields=status,reporter,assignee",
    )
    if data is None:
        raise JiraRequestError("JIRA issue 查询返回了空响应。")
    return data


def get_transitions(config: JiraConfig, issue_key: str) -> list[dict[str, Any]]:
    key = encoded_issue_path(issue_key)
    data = request_json(config, "GET", f"/rest/api/2/issue/{key}/transitions")
    transitions = (data or {}).get("transitions", [])
    if not isinstance(transitions, list):
        raise JiraRequestError("JIRA transitions 响应格式无效。")
    return transitions


def user_summary(user: Any) -> dict[str, str] | None:
    if not isinstance(user, dict):
        return None
    return {
        "username": str(user.get("name") or ""),
        "display_name": str(user.get("displayName") or ""),
    }


def inspect_issue(config: JiraConfig, issue_key: str) -> dict[str, Any]:
    issue = get_issue(config, issue_key)
    fields = issue.get("fields") or {}
    status = fields.get("status") or {}
    transitions = get_transitions(config, issue_key)
    return {
        "issue_key": issue_key,
        "current_status": {
            "id": str(status.get("id") or ""),
            "name": str(status.get("name") or ""),
        },
        "reporter": user_summary(fields.get("reporter")),
        "assignee": user_summary(fields.get("assignee")),
        "available_transitions": [
            {
                "id": str(transition.get("id") or ""),
                "button_name": str(transition.get("name") or ""),
                "destination_status": {
                    "id": str((transition.get("to") or {}).get("id") or ""),
                    "name": str((transition.get("to") or {}).get("name") or ""),
                },
            }
            for transition in transitions
        ],
    }


def resolve_transition(
    transitions: list[dict[str, Any]], transition_id: str
) -> dict[str, Any]:
    matches = [item for item in transitions if str(item.get("id")) == transition_id]
    if len(matches) != 1:
        available = ", ".join(str(item.get("id")) for item in transitions) or "无"
        raise ValueError(
            f"transition ID {transition_id!r} 当前不可用；可用 ID：{available}。"
        )
    transition = matches[0]
    destination = transition.get("to")
    if not isinstance(destination, dict) or not destination.get("name"):
        raise ValueError(f"transition ID {transition_id!r} 缺少目标状态。")
    return transition


def resolve_transition_by_name(
    transitions: list[dict[str, Any]], transition_name: str
) -> dict[str, Any]:
    """Resolve one unambiguous transition by its exact button name."""
    requested = transition_name.strip()
    if not requested:
        raise ValueError("transition name 不能为空。")
    matches = [item for item in transitions if str(item.get("name") or "") == requested]
    if len(matches) != 1:
        available = (
            ", ".join(
                f"{item.get('id')} / {item.get('name')} -> "
                f"{(item.get('to') or {}).get('name')}"
                for item in transitions
            )
            or "无"
        )
        if not matches:
            reason = "没有匹配项"
        else:
            reason = f"存在 {len(matches)} 个匹配项"
        raise ValueError(
            f"无法唯一解析 transition name {requested!r}（{reason}）；"
            f"当前可用 transitions：{available}。"
        )
    return matches[0]


def resolve_assignee(assignee: str, issue: dict[str, Any], config: JiraConfig) -> str:
    requested = assignee.strip()
    if not requested:
        raise ValueError("assignee 不能为空。")
    if requested.lower() == "@me":
        return config.user
    if requested.lower() == "@reporter":
        reporter = ((issue.get("fields") or {}).get("reporter") or {}).get("name")
        if not reporter:
            raise ValueError("当前 issue 没有可解析的报告人用户名。")
        return str(reporter)
    if requested.startswith("@"):
        raise ValueError("未知 assignee 特殊值；仅支持 @reporter、@me 或明确用户名。")
    return requested


def read_comment(path: Path) -> str:
    try:
        comment = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"无法读取 comment 文件 {path}：{exc}") from exc
    if not comment:
        raise ValueError("comment 不能为空。")
    return comment


def apply_updates(
    config: JiraConfig,
    issue_key: str,
    comment: str | None,
    transition_id: str,
    requested_assignee: str,
    target_status: str | None = None,
    next_transition_names: list[str] | None = None,
) -> dict[str, Any]:
    """Optionally comment, follow a guarded transition path, assign, then verify."""
    if comment is not None and not comment.strip():
        raise ValueError("comment 不能为空。")
    issue = get_issue(config, issue_key)
    transitions = get_transitions(config, issue_key)
    initial_transition = resolve_transition(transitions, transition_id)
    assignee = resolve_assignee(requested_assignee, issue, config)
    requested_target = target_status.strip() if target_status is not None else None
    if target_status is not None and not requested_target:
        raise ValueError("target status 不能为空。")
    requested_next_names = [name.strip() for name in (next_transition_names or [])]
    if any(not name for name in requested_next_names):
        raise ValueError("next transition name 不能为空。")
    if requested_next_names and not requested_target:
        raise ValueError("多步 transition 必须同时提供最终 target status。")
    key = encoded_issue_path(issue_key)
    initial_destination = str((initial_transition.get("to") or {}).get("name"))
    expected_status = requested_target or initial_destination
    completed: list[str] = []
    transition_path: list[dict[str, str]] = []

    def perform_write(label: str, method: str, path: str, body: dict[str, Any]) -> None:
        try:
            request_json(config, method, path, body)
        except JiraRequestError as exc:
            if completed:
                raise PartialUpdateError(completed, label, exc) from exc
            raise
        completed.append(label)
        print(f"已完成：{label}")

    def perform_transition(transition: dict[str, Any]) -> None:
        resolved_id = str(transition.get("id") or "")
        button = str(transition.get("name") or "")
        destination = str((transition.get("to") or {}).get("name") or "")
        perform_write(
            f"执行 transition {resolved_id} -> {destination}",
            "POST",
            f"/rest/api/2/issue/{key}/transitions",
            {"transition": {"id": resolved_id}},
        )
        transition_path.append(
            {
                "id": resolved_id,
                "button_name": button,
                "destination_status": destination,
            }
        )

    if comment is not None:
        perform_write(
            "添加 comment",
            "POST",
            f"/rest/api/2/issue/{key}/comment",
            {"body": comment},
        )
    perform_transition(initial_transition)

    for requested_name in requested_next_names:
        try:
            next_transitions = get_transitions(config, issue_key)
            next_transition = resolve_transition_by_name(
                next_transitions, requested_name
            )
        except (JiraRequestError, ValueError) as exc:
            raise PartialUpdateError(
                completed,
                f"解析 transition name {requested_name!r}",
                exc,
            ) from exc
        perform_transition(next_transition)

    perform_write(
        f"转派给 {assignee}",
        "PUT",
        f"/rest/api/2/issue/{key}/assignee",
        {"name": assignee},
    )

    try:
        final_issue = get_issue(config, issue_key)
    except JiraRequestError as exc:
        raise PartialUpdateError(completed, "读取最终状态", exc) from exc

    final_fields = final_issue.get("fields") or {}
    final_status = str((final_fields.get("status") or {}).get("name") or "")
    final_assignee = str((final_fields.get("assignee") or {}).get("name") or "")
    if final_status != expected_status or final_assignee != assignee:
        raise PartialUpdateError(
            completed,
            "验证最终状态",
            RuntimeError(
                f"期望状态={expected_status!r}、经办人={assignee!r}；"
                f"实际状态={final_status!r}、经办人={final_assignee!r}"
            ),
        )

    return {
        "issue_key": issue_key,
        "comment": "created" if comment is not None else "skipped_existing",
        "assignee": final_assignee,
        "transition_id": transition_path[-1]["id"],
        "transition_button": transition_path[-1]["button_name"],
        "transition_path": transition_path,
        "status": final_status,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="只读检查或经确认后更新一个 JIRA issue"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="只读检查 issue 和可用流转")
    inspect_parser.add_argument("issue_key", help="JIRA issue key，如 JIRA-1234")

    apply_parser = subparsers.add_parser(
        "apply", help="执行已确认的 comment、转派和流转"
    )
    apply_parser.add_argument("issue_key", help="JIRA issue key，如 JIRA-1234")
    apply_parser.add_argument("--comment-file", required=True, type=Path)
    apply_parser.add_argument("--transition-id", required=True)
    apply_parser.add_argument(
        "--target-status",
        help=("已确认的最终状态名；多步 transition 时必填并用于最终状态校验"),
    )
    apply_parser.add_argument(
        "--next-transition-name",
        action="append",
        default=[],
        help=(
            "首步之后已确认的 transition 按钮名；按执行顺序重复提供，"
            "每一步必须精确且唯一匹配"
        ),
    )
    apply_parser.add_argument("--assignee", required=True)
    apply_parser.add_argument(
        "--confirm",
        required=True,
        help="安全确认值；必须与 issue key 完全一致",
    )

    resume_parser = subparsers.add_parser(
        "resume",
        help="在已确认 comment 成功的部分更新后继续流转，不重复添加 comment",
    )
    resume_parser.add_argument("issue_key", help="JIRA issue key，如 JIRA-1234")
    resume_parser.add_argument("--transition-id", required=True)
    resume_parser.add_argument(
        "--target-status",
        help=("已确认的最终状态名；多步 transition 时必填并用于最终状态校验"),
    )
    resume_parser.add_argument(
        "--next-transition-name",
        action="append",
        default=[],
        help=(
            "首步之后已确认的 transition 按钮名；按执行顺序重复提供，"
            "每一步必须精确且唯一匹配"
        ),
    )
    resume_parser.add_argument("--assignee", required=True)
    resume_parser.add_argument(
        "--confirm",
        required=True,
        help="安全确认值；必须与 issue key 完全一致",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"apply", "resume"} and args.confirm != args.issue_key:
            raise ValueError("--confirm 必须与 issue key 完全一致，拒绝执行写操作。")

        config = load_config()
        if args.command == "inspect":
            result = inspect_issue(config, args.issue_key)
        else:
            comment = (
                read_comment(args.comment_file) if args.command == "apply" else None
            )
            result = apply_updates(
                config,
                args.issue_key,
                comment,
                args.transition_id,
                args.assignee,
                args.target_status,
                args.next_transition_name,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (
        ConfigurationError,
        JiraRequestError,
        PartialUpdateError,
        ValueError,
    ) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
