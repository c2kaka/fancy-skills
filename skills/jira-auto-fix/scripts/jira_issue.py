#!/usr/bin/env python3
"""Read JIRA issues and download same-origin attachments using local .env credentials."""

from __future__ import annotations

import argparse
import base64
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SKILL_DIR / ".env"
REQUIRED_SETTINGS = ("JIRA_BASE_URL", "JIRA_USER", "JIRA_PASSWORD")
MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 30


class ConfigurationError(ValueError):
    """Raised when the skill-local .env file is missing or invalid."""


class JiraRequestError(RuntimeError):
    """Raised when a read-only JIRA request fails."""


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    user: str
    password: str


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE entries without executing shell code or interpolation."""
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

    return JiraConfig(
        base_url=base_url,
        user=values["JIRA_USER"],
        password=values["JIRA_PASSWORD"],
    )


def authorization_value(config: JiraConfig) -> str:
    token = base64.b64encode(f"{config.user}:{config.password}".encode()).decode()
    return f"Basic {token}"


def open_read_only_request(config: JiraConfig, url: str):
    request = urllib.request.Request(url, method="GET")
    request.add_header("Authorization", authorization_value(config))
    request.add_header(
        "Accept", "application/json, image/*, text/plain, application/octet-stream"
    )
    try:
        return urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise JiraRequestError(
                "认证失败（401）：请检查 .env 中的 JIRA_USER 和 JIRA_PASSWORD。"
            ) from exc
        if exc.code == 403:
            raise JiraRequestError("权限不足（403）：当前账号无权读取该资源。") from exc
        if exc.code == 404:
            raise JiraRequestError(
                "未找到（404）：资源不存在或当前账号无权访问。"
            ) from exc
        body = exc.read().decode(errors="replace")
        raise JiraRequestError(f"JIRA 请求失败，HTTP {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise JiraRequestError(
            f"网络错误：无法连接 JIRA（{exc.reason}）。请检查 .env、VPN 和网络。"
        ) from exc


def api_get_json(
    config: JiraConfig,
    path: str,
    params: dict[str, str] | None = None,
):
    url = config.base_url + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with open_read_only_request(config, url) as response:
        try:
            return json.loads(response.read().decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JiraRequestError("JIRA 返回了无法解析的 JSON 响应。") from exc


def fetch_issue(config: JiraConfig, issue_key: str):
    encoded_key = urllib.parse.quote(issue_key, safe="")
    return api_get_json(
        config,
        f"/rest/api/2/issue/{encoded_key}",
        params={"expand": "renderedFields"},
    )


def origin(url: str) -> tuple[str, str, int]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise JiraRequestError("附件 URL 必须是有效的 HTTPS 地址。")
    if parsed.username or parsed.password:
        raise JiraRequestError("附件 URL 不能包含凭证。")
    return parsed.scheme, parsed.hostname.lower(), parsed.port or 443


def download_attachment(
    config: JiraConfig,
    attachment_url: str,
    output_path: Path,
    overwrite: bool = False,
) -> tuple[int, str | None]:
    if origin(attachment_url) != origin(config.base_url):
        raise JiraRequestError("拒绝下载：附件 URL 与配置的 JIRA 不是同一来源。")
    if output_path.exists() and not overwrite:
        raise JiraRequestError(
            f"输出文件已存在：{output_path}。如需覆盖请添加 --overwrite。"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with open_read_only_request(config, attachment_url) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError as exc:
                    raise JiraRequestError(
                        "附件响应包含无效的 Content-Length。"
                    ) from exc
                if declared_size > MAX_ATTACHMENT_BYTES:
                    raise JiraRequestError(
                        f"附件超过 {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MiB 限制。"
                    )

            media_type = response.headers.get("Content-Type")
            total = 0
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ATTACHMENT_BYTES:
                        raise JiraRequestError(
                            f"附件超过 {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MiB 限制。"
                        )
                    temporary_file.write(chunk)

        os.replace(temporary_path, output_path)
        temporary_path = None
        return total, media_type
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="读取 JIRA Issue 和附件（只读）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    query_parser = subparsers.add_parser("query", help="查询 Issue 详情")
    query_parser.add_argument("issue_key", help="JIRA 号，如 JIRA-1234")
    query_parser.add_argument("--json", action="store_true", help="输出 API 原始 JSON")
    query_parser.add_argument(
        "--comments",
        choices=(0, 1),
        type=int,
        default=1,
        help="是否显示评论：1 显示（默认），0 不显示",
    )

    download_parser = subparsers.add_parser("download", help="下载同源 JIRA 附件")
    download_parser.add_argument("attachment_url", help="查询结果中的附件 URL")
    download_parser.add_argument("output_path", type=Path, help="本地输出路径")
    download_parser.add_argument(
        "--overwrite", action="store_true", help="允许覆盖已有文件"
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        config = load_config()
        if args.command == "query":
            data = fetch_issue(config, args.issue_key)
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(format_issue(data, config.base_url, bool(args.comments)))
            return

        size, media_type = download_attachment(
            config,
            args.attachment_url,
            args.output_path,
            overwrite=args.overwrite,
        )
        print(
            f"附件已下载：{args.output_path} ({size} bytes, {media_type or 'unknown'})"
        )
    except (ConfigurationError, JiraRequestError) as exc:
        raise SystemExit(f"错误：{exc}") from exc


if __name__ == "__main__":
    main()
