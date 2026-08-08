#!/usr/bin/env python3
"""Query a JIRA issue using credentials from the skill-local .env file.

Only the Python standard library is required. This script performs GET requests
only and never modifies the issue.
"""

from __future__ import annotations

import argparse
import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SKILL_DIR / ".env"
REQUIRED_SETTINGS = ("JIRA_BASE_URL", "JIRA_USER", "JIRA_PASSWORD")


class ConfigurationError(ValueError):
    """Raised when the skill-local .env file is missing or invalid."""


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    user: str
    password: str


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE entries without executing shell code."""
    if not path.is_file():
        raise ConfigurationError(
            f"未找到配置文件：{path}。请复制 .env.example 为 .env 后填写配置。"
        )

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigurationError(f"无法读取配置文件 {path}：{exc}") from exc

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
    parsed_url = urllib.parse.urlsplit(base_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ConfigurationError("JIRA_BASE_URL 必须是有效的 HTTPS 地址。")
    if (
        parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ConfigurationError("JIRA_BASE_URL 不能包含凭证、查询参数或 URL 片段。")

    return JiraConfig(
        base_url=base_url,
        user=values["JIRA_USER"],
        password=values["JIRA_PASSWORD"],
    )


def api_get(config: JiraConfig, path: str, params: dict[str, str] | None = None):
    url = config.base_url + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    token = base64.b64encode(f"{config.user}:{config.password}".encode()).decode()
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Basic {token}")
    request.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise SystemExit(
                "认证失败（401）：请检查 .env 中的 JIRA_USER 和 JIRA_PASSWORD。"
            )
        if exc.code == 404:
            raise SystemExit("未找到（404）：Issue 不存在或当前账号无权访问。")
        body = exc.read().decode(errors="replace")
        raise SystemExit(f"JIRA 请求失败，HTTP {exc.code}: {body[:500]}")
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"网络错误：无法连接 JIRA（{exc.reason}）。请检查 .env、VPN 和网络。"
        )


def fetch_issue(config: JiraConfig, issue_key: str):
    encoded_key = urllib.parse.quote(issue_key, safe="")
    return api_get(
        config,
        f"/rest/api/2/issue/{encoded_key}",
        params={"expand": "renderedFields"},
    )


def name_of(field):
    if isinstance(field, dict):
        return field.get("displayName") or field.get("name") or field.get("value")
    return field


def join_names(fields) -> str:
    names = [
        str(name) for field in fields or [] if (name := name_of(field)) is not None
    ]
    return ", ".join(names) or "(无)"


def format_issue(data, base_url: str, show_comments: bool) -> str:
    fields = data.get("fields", {})
    key = data.get("key", "")
    lines = [
        "=" * 60,
        f"  {key}  —  {fields.get('summary', '(无摘要)')}",
        "=" * 60,
        f"链接      : {base_url}/browse/{key}",
        f"类型      : {name_of(fields.get('issuetype'))}",
        f"状态      : {name_of(fields.get('status'))}",
        f"优先级    : {name_of(fields.get('priority'))}",
        f"报告人    : {name_of(fields.get('reporter'))}",
        f"经办人    : {name_of(fields.get('assignee')) or '(未分配)'}",
        f"组件      : {join_names(fields.get('components'))}",
        f"标签      : {', '.join(fields.get('labels') or []) or '(无)'}",
        f"修复版本  : {join_names(fields.get('fixVersions'))}",
        f"创建时间  : {fields.get('created')}",
        f"更新时间  : {fields.get('updated')}",
    ]

    environment = fields.get("environment")
    if environment:
        lines.extend(("", "【运行环境】", str(environment).strip()))

    description = fields.get("description")
    lines.extend(
        ("", "【描述】", str(description).strip() if description else "(无描述)")
    )

    attachments = fields.get("attachment") or []
    if attachments:
        lines.extend(("", f"【附件】({len(attachments)} 个)"))
        for attachment in attachments:
            lines.append(
                f"  - {attachment.get('filename')}  ({attachment.get('size')} bytes)"
            )
            lines.append(f"    {attachment.get('content')}")

    if show_comments:
        comments = (fields.get("comment") or {}).get("comments") or []
        lines.extend(("", f"【评论】({len(comments)} 条)"))
        if not comments:
            lines.append("  (无评论)")
        for comment in comments:
            author = name_of(comment.get("author"))
            lines.append(f"  --- {author} @ {comment.get('created')} ---")
            body = str(comment.get("body") or "").strip().replace("\n", "\n  ")
            lines.append("  " + body)

    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="查询 JIRA Issue 详情（只读）")
    parser.add_argument("issue_key", help="JIRA 号，如 JIRA-1234")
    parser.add_argument("--json", action="store_true", help="输出 API 原始 JSON")
    parser.add_argument(
        "--comments",
        choices=(0, 1),
        type=int,
        default=1,
        help="是否显示评论：1 显示（默认），0 不显示",
    )
    args = parser.parse_args()

    try:
        config = load_config()
    except ConfigurationError as exc:
        raise SystemExit(f"配置错误：{exc}") from exc

    data = fetch_issue(config, args.issue_key)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(format_issue(data, config.base_url, show_comments=bool(args.comments)))


if __name__ == "__main__":
    main()
