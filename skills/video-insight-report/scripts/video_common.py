#!/usr/bin/env python3
"""Shared deterministic helpers for video-insight-report."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


class VideoInsightError(RuntimeError):
    """Raised when a deterministic video-report invariant fails."""


@dataclass(frozen=True)
class VideoTarget:
    platform: str
    video_id: str
    url: str


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
BILIBILI_HOSTS = {
    "bilibili.com",
    "www.bilibili.com",
    "m.bilibili.com",
    "b23.tv",
    "www.b23.tv",
}
BVID_PATTERN = re.compile(r"(?i)\b(BV[0-9A-Za-z]{10})\b")
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")


def parse_video_target(url_value: str) -> VideoTarget:
    url = url_value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise VideoInsightError("视频链接必须是公开的 http(s) URL。")
    if parsed.username or parsed.password:
        raise VideoInsightError("视频链接不能包含用户名或密码。")
    host = parsed.hostname.lower()
    query = parse_qs(parsed.query)

    if host in YOUTUBE_HOSTS:
        if "list" in query:
            raise VideoInsightError("首版不接受播放列表或带 list 参数的视频链接。")
        if host == "youtu.be":
            video_id = parsed.path.strip("/").split("/", 1)[0]
        elif parsed.path == "/watch":
            video_id = (query.get("v") or [""])[0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            video_id = (
                parts[1]
                if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}
                else ""
            )
        if not re.fullmatch(r"[0-9A-Za-z_-]{6,20}", video_id):
            raise VideoInsightError("无法从 YouTube URL 解析单个视频 ID。")
        return VideoTarget("youtube", video_id, url)

    if host in BILIBILI_HOSTS:
        match = BVID_PATTERN.search(url)
        if match:
            video_id = match.group(1)
        elif host in {"b23.tv", "www.b23.tv"}:
            video_id = f"short-{hashlib.sha256(url.encode()).hexdigest()[:12]}"
        else:
            raise VideoInsightError("无法从 Bilibili URL 解析 BV 号。")
        return VideoTarget("bilibili", video_id, url)

    raise VideoInsightError("首版只支持公开 YouTube 或 Bilibili 视频链接。")


def safe_identifier(value: str, *, label: str = "标识") -> str:
    candidate = value.strip().lower()
    if not SAFE_ID_PATTERN.fullmatch(candidate):
        raise VideoInsightError(f"{label} 只能包含小写字母、数字、下划线和连字符。")
    return candidate


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Any) -> None:
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )
    atomic_write_bytes(path, payload)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VideoInsightError(f"无法读取 JSON {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_within(path: Path, root: Path, *, must_exist: bool = False) -> Path:
    root_resolved = root.expanduser().resolve()
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = root_resolved / candidate
    if must_exist:
        current = candidate
        while current != root_resolved and current != current.parent:
            if current.is_symlink():
                raise VideoInsightError(f"资源路径不能经过符号链接：{path}")
            current = current.parent
    resolved = candidate.resolve(strict=must_exist)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise VideoInsightError(f"路径越过运行目录：{path}") from exc
    return resolved


def command_path(name: str) -> str | None:
    return shutil.which(name)


def tool_version(name: str, *version_args: str) -> dict[str, Any]:
    executable = command_path(name)
    result: dict[str, Any] = {
        "name": name,
        "available": bool(executable),
        "path": executable,
        "version": None,
    }
    if not executable:
        return result
    args = [executable, *(version_args or ("--version",))]
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["available"] = False
        result["error"] = str(exc)[:240]
        return result
    output = (completed.stdout or completed.stderr).strip().splitlines()
    result["version"] = output[0][:240] if output else None
    result["exit_code"] = completed.returncode
    return result


def run_command(
    args: list[str], *, timeout: int = 1800, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    if not args or not Path(args[0]).name:
        raise VideoInsightError("命令不能为空。")
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VideoInsightError(f"命令无法完成：{Path(args[0]).name}: {exc}") from exc
    return completed


def require_command_success(
    completed: subprocess.CompletedProcess[str], *, label: str
) -> str:
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout).strip()[-2000:]
        raise VideoInsightError(
            f"{label}失败（exit {completed.returncode}）：{diagnostic}"
        )
    return completed.stdout


def extract_json_payload(text: str) -> Any:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            return value
        except json.JSONDecodeError:
            continue
    raise VideoInsightError("命令输出中没有可解析的 JSON。")


def media_files(root: Path, suffixes: set[str]) -> list[Path]:
    normalized = {suffix.lower() for suffix in suffixes}
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.lower() in normalized
        and path.stat().st_size > 0
    )
