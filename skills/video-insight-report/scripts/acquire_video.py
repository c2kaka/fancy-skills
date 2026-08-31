#!/usr/bin/env python3
"""Platform-safe acquisition for one public YouTube or Bilibili video."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from video_common import (
    VideoInsightError,
    atomic_write_json,
    command_path,
    extract_json_payload,
    load_json,
    media_files,
    parse_video_target,
    require_command_success,
    run_command,
    tool_version,
)

VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
AUDIO_SUFFIXES = {".wav", ".m4a", ".mp3", ".aac", ".opus", ".ogg", ".webm"}


def safe_diagnostic(value: str) -> str:
    text = re.sub(r"https?://\S+", "[URL_REDACTED]", value)
    text = re.sub(
        r"(?i)\b(SESSDATA|cookie|token|authorization)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )
    return text.strip()[-1600:]


def emit(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def require_tool(name: str) -> str:
    path = command_path(name)
    if not path:
        raise VideoInsightError(f"缺少必需命令：{name}")
    return path


def acquisition_root(run_dir: Path) -> Path:
    root = run_dir.expanduser().resolve() / "acquisition"
    root.mkdir(parents=True, exist_ok=True)
    return root


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    target = parse_video_target(args.url)
    names = ["ffmpeg", "ffprobe", "agent-reach"]
    if target.platform == "youtube":
        names.extend(["yt-dlp", "opencli"])
    else:
        names.extend(["bili", "opencli"])
    tools = [
        tool_version(name, "-version")
        if name in {"ffmpeg", "ffprobe"}
        else tool_version(name)
        for name in names
    ]
    required = (
        {"ffmpeg", "ffprobe", "yt-dlp"}
        if target.platform == "youtube"
        else {"ffmpeg", "ffprobe", "bili", "opencli"}
    )
    missing = sorted(
        item["name"]
        for item in tools
        if item["name"] in required and not item["available"]
    )
    return {
        "status": "BLOCKED" if missing else "READY",
        "target": target.__dict__,
        "tools": tools,
        "missing_required_tools": missing,
        "download_authorized": False,
        "notes": [
            "Resource size requires metadata and format inspection before media download.",
            "Bilibili media acquisition is not accepted until a real frame is extracted.",
        ],
    }


def normalize_metadata(
    raw: dict[str, Any], platform: str, original_url: str
) -> dict[str, Any]:
    if platform == "bilibili":
        data = raw.get("data")
        if isinstance(data, dict) and isinstance(data.get("video"), dict):
            raw = data["video"]
    if raw.get("_type") in {"playlist", "multi_video"} or raw.get("entries"):
        raise VideoInsightError("目标解析为播放列表或多视频集合，超出首版范围。")

    aliases = {
        "video_id": ("id", "bvid", "bv_id", "aid"),
        "title": ("title", "name"),
        "creator": ("uploader", "author", "owner_name", "up_name"),
        "duration_seconds": ("duration", "duration_seconds"),
        "canonical_url": ("webpage_url", "url", "canonical_url"),
        "language": ("language", "lang"),
    }
    normalized: dict[str, Any] = {"platform": platform}
    for target_key, candidates in aliases.items():
        normalized[target_key] = next(
            (raw[key] for key in candidates if raw.get(key) not in (None, "")), None
        )
    normalized["canonical_url"] = normalized.get("canonical_url") or original_url
    duration = normalized.get("duration_seconds")
    if isinstance(duration, str):
        try:
            if ":" in duration:
                pieces = [float(piece) for piece in duration.split(":")]
                duration = sum(
                    value * (60**index) for index, value in enumerate(reversed(pieces))
                )
            else:
                duration = float(duration)
        except ValueError:
            duration = None
    normalized["duration_seconds"] = duration
    if platform == "bilibili" and isinstance(raw.get("owner"), dict):
        normalized["creator"] = raw["owner"].get("name")

    size_candidates: list[int] = []
    for item in raw.get("requested_formats") or []:
        size = item.get("filesize") or item.get("filesize_approx")
        if isinstance(size, (int, float)) and size > 0:
            size_candidates.append(int(size))
    normalized["estimated_download_bytes"] = (
        sum(size_candidates) or raw.get("filesize") or raw.get("filesize_approx")
    )
    if not normalized.get("video_id") or not normalized.get("title"):
        raise VideoInsightError("平台元数据缺少视频 ID 或标题，不能视为成功。")
    return normalized


def metadata(args: argparse.Namespace) -> dict[str, Any]:
    target = parse_video_target(args.url)
    root = acquisition_root(Path(args.run_dir))
    if target.platform == "youtube":
        completed = run_command(
            [
                require_tool("yt-dlp"),
                "--dump-single-json",
                "--no-playlist",
                "--socket-timeout",
                "20",
                "--retries",
                "2",
                "--extractor-retries",
                "2",
                target.url,
            ],
            timeout=args.timeout,
        )
        raw_text = require_command_success(completed, label="YouTube 元数据获取")
        raw = extract_json_payload(raw_text)
    else:
        completed = run_command(
            [require_tool("bili"), "video", target.url, "--json"],
            timeout=args.timeout,
        )
        raw_text = require_command_success(completed, label="Bilibili 元数据获取")
        raw = extract_json_payload(raw_text)
    if not isinstance(raw, dict):
        raise VideoInsightError("平台元数据必须是 JSON 对象。")
    normalized = normalize_metadata(raw, target.platform, target.url)
    atomic_write_json(root / "metadata.raw.json", raw)
    atomic_write_json(root / "source.json", normalized)
    return {"status": "READY", "source": normalized, "path": str(root / "source.json")}


def nonempty_subtitle_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.suffix.lower() in {".vtt", ".srt", ".json"}
        and path.is_file()
        and path.stat().st_size > 20
    )


def has_timeline_segments(value: Any) -> bool:
    queue = [value]
    visited = 0
    while queue and visited < 5000:
        current = queue.pop(0)
        visited += 1
        if isinstance(current, dict):
            start = next(
                (
                    current[key]
                    for key in ("start_seconds", "start", "from", "begin")
                    if key in current
                ),
                None,
            )
            end = next(
                (
                    current[key]
                    for key in ("end_seconds", "end", "to", "finish")
                    if key in current
                ),
                None,
            )
            text = next(
                (
                    current[key]
                    for key in ("text", "content", "body", "caption")
                    if current.get(key)
                ),
                None,
            )
            if start is not None and end is not None and str(text or "").strip():
                try:
                    if float(start) >= 0 and float(end) >= float(start):
                        return True
                except (TypeError, ValueError):
                    pass
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    return False


def subtitle_file_has_cues(path: Path) -> bool:
    if path.suffix.lower() == ".json":
        try:
            return has_timeline_segments(load_json(path))
        except VideoInsightError:
            return False
    content = path.read_text(encoding="utf-8", errors="replace")
    return "-->" in content and any(
        line.strip()
        for line in content.splitlines()
        if "-->" not in line and not line.startswith("WEBVTT")
    )


def subtitles(args: argparse.Namespace) -> dict[str, Any]:
    target = parse_video_target(args.url)
    root = acquisition_root(Path(args.run_dir)) / "subtitles"
    root.mkdir(parents=True, exist_ok=True)
    diagnostic = ""
    attempts: list[dict[str, Any]] = []
    if target.platform == "youtube":
        output_template = str(root / "source.%(id)s.%(language)s.%(ext)s")
        completed = run_command(
            [
                require_tool("yt-dlp"),
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                args.languages,
                "--sub-format",
                "vtt",
                "--skip-download",
                "--no-playlist",
                "--output",
                output_template,
                target.url,
            ],
            timeout=args.timeout,
        )
        diagnostic = safe_diagnostic(completed.stderr or completed.stdout)
        files = [
            path
            for path in nonempty_subtitle_files(root)
            if path.suffix.lower() in {".vtt", ".srt"} and subtitle_file_has_cues(path)
        ]
        attempts.append(
            {
                "adapter": "yt-dlp",
                "exit_code": completed.returncode,
                "usable_timeline": bool(files),
                "diagnostic": diagnostic or None,
            }
        )
        if not files and args.allow_browser_fallback:
            opencli = require_tool("opencli")
            for _ in range(3):
                fallback = run_command(
                    [opencli, "youtube", "transcript", target.url, "-f", "json"],
                    timeout=args.timeout,
                )
                if fallback.returncode != 0:
                    diagnostic = safe_diagnostic(fallback.stderr or fallback.stdout)
                    attempts.append(
                        {
                            "adapter": "opencli-youtube",
                            "exit_code": fallback.returncode,
                            "usable_timeline": False,
                            "diagnostic": diagnostic or None,
                        }
                    )
                    continue
                try:
                    payload = extract_json_payload(fallback.stdout)
                except VideoInsightError as exc:
                    diagnostic = safe_diagnostic(str(exc))
                    attempts.append(
                        {
                            "adapter": "opencli-youtube",
                            "exit_code": fallback.returncode,
                            "usable_timeline": False,
                            "diagnostic": diagnostic,
                        }
                    )
                    continue
                usable = has_timeline_segments(payload)
                attempts.append(
                    {
                        "adapter": "opencli-youtube",
                        "exit_code": fallback.returncode,
                        "usable_timeline": usable,
                        "diagnostic": None,
                    }
                )
                if usable:
                    atomic_write_json(root / "opencli-transcript.json", payload)
                    files = [root / "opencli-transcript.json"]
                    break
    else:
        opencli = require_tool("opencli")
        bvid_or_url = (
            target.video_id if not target.video_id.startswith("short-") else target.url
        )
        completed = run_command(
            [
                opencli,
                "bilibili",
                "subtitle",
                bvid_or_url,
                "-f",
                "json",
                "--window",
                "background",
                "--site-session",
                "ephemeral",
                "--keep-tab",
                "false",
            ],
            timeout=args.timeout,
        )
        diagnostic = safe_diagnostic(completed.stderr or completed.stdout)
        files = []
        opencli_usable = False
        if completed.returncode == 0:
            try:
                payload = extract_json_payload(completed.stdout)
                opencli_usable = has_timeline_segments(payload)
                if opencli_usable:
                    atomic_write_json(root / "opencli-subtitle.json", payload)
                    files = [root / "opencli-subtitle.json"]
            except VideoInsightError as exc:
                diagnostic = safe_diagnostic(str(exc))
        attempts.append(
            {
                "adapter": "opencli-bilibili",
                "exit_code": completed.returncode,
                "usable_timeline": opencli_usable,
                "diagnostic": diagnostic or None,
            }
        )
        if not files:
            fallback = run_command(
                [
                    require_tool("bili"),
                    "video",
                    target.url,
                    "--subtitle-timeline",
                    "--subtitle-format",
                    "srt",
                    "--json",
                ],
                timeout=args.timeout,
            )
            diagnostic = safe_diagnostic(fallback.stderr or fallback.stdout)
            fallback_usable = False
            if fallback.returncode == 0:
                try:
                    payload = extract_json_payload(fallback.stdout)
                    fallback_usable = has_timeline_segments(payload)
                    if fallback_usable:
                        atomic_write_json(root / "bili-subtitle.json", payload)
                        files = [root / "bili-subtitle.json"]
                except VideoInsightError as exc:
                    diagnostic = safe_diagnostic(str(exc))
            attempts.append(
                {
                    "adapter": "bili-cli",
                    "exit_code": fallback.returncode,
                    "usable_timeline": fallback_usable,
                    "diagnostic": diagnostic or None,
                }
            )
    return {
        "status": "READY" if files else "UNAVAILABLE",
        "files": [str(path) for path in files],
        "diagnostic": None if files else diagnostic,
        "reason": None if files else "no_usable_timeline",
        "attempts": attempts,
    }


def source_bvid(target_url: str, run_dir: Path) -> str:
    target = parse_video_target(target_url)
    if not target.video_id.startswith("short-"):
        return target.video_id
    source_path = acquisition_root(run_dir) / "source.json"
    if not source_path.exists():
        raise VideoInsightError(
            "Bilibili 短链下载前必须先运行 metadata 解析真实 BV 号。"
        )
    source = load_json(source_path)
    candidate = str(source.get("video_id") or "")
    if not candidate.lower().startswith("bv"):
        raise VideoInsightError("元数据没有提供可用 BV 号。")
    return candidate


def download_video(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_download:
        raise VideoInsightError("媒体下载需要显式传入 --allow-download。")
    target = parse_video_target(args.url)
    run_dir = Path(args.run_dir).expanduser().resolve()
    root = acquisition_root(run_dir) / "video"
    root.mkdir(parents=True, exist_ok=True)
    if target.platform == "youtube":
        template = str(root / "source.%(ext)s")
        completed = run_command(
            [
                require_tool("yt-dlp"),
                "--no-playlist",
                "--format",
                "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "--merge-output-format",
                "mp4",
                "--output",
                template,
                target.url,
            ],
            timeout=args.timeout,
        )
    else:
        bvid = source_bvid(target.url, run_dir)
        completed = run_command(
            [
                require_tool("opencli"),
                "bilibili",
                "download",
                bvid,
                "--output",
                str(root),
                "--quality",
                args.quality,
                "-f",
                "json",
                "--window",
                "background",
                "--site-session",
                "ephemeral",
                "--keep-tab",
                "false",
            ],
            timeout=args.timeout,
        )
    require_command_success(completed, label=f"{target.platform} 视频下载")
    files = media_files(root, VIDEO_SUFFIXES)
    if not files:
        raise VideoInsightError("下载命令完成但没有得到非空视频文件。")
    return {
        "status": "READY",
        "platform": target.platform,
        "files": [str(path) for path in files],
    }


def convert_audio(source: Path, output: Path) -> None:
    completed = run_command(
        [
            require_tool("ffmpeg"),
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output),
        ],
        timeout=1800,
    )
    require_command_success(completed, label="音频标准化")
    if not output.exists() or output.stat().st_size == 0:
        raise VideoInsightError("音频标准化没有生成非空 WAV。")


def download_audio(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_download:
        raise VideoInsightError("音频下载需要显式传入 --allow-download。")
    target = parse_video_target(args.url)
    run_dir = Path(args.run_dir).expanduser().resolve()
    root = acquisition_root(run_dir) / "audio"
    root.mkdir(parents=True, exist_ok=True)
    if target.platform == "youtube":
        template = str(root / "source.%(ext)s")
        completed = run_command(
            [
                require_tool("yt-dlp"),
                "--no-playlist",
                "--format",
                "bestaudio/best",
                "--output",
                template,
                target.url,
            ],
            timeout=args.timeout,
        )
    else:
        bvid = source_bvid(target.url, run_dir)
        completed = run_command(
            [require_tool("bili"), "audio", bvid, "--no-split", "--output", str(root)],
            timeout=args.timeout,
        )
    require_command_success(completed, label=f"{target.platform} 音频下载")
    sources = [
        path for path in media_files(root, AUDIO_SUFFIXES) if path.name != "audio.wav"
    ]
    if not sources:
        raise VideoInsightError("下载命令完成但没有得到非空音频文件。")
    output = root / "audio.wav"
    convert_audio(sources[0], output)
    return {"status": "READY", "platform": target.platform, "path": str(output)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--url", required=True)
    preflight_parser.set_defaults(handler=preflight)

    for name, handler in (
        ("metadata", metadata),
        ("subtitles", subtitles),
        ("video", download_video),
        ("audio", download_audio),
    ):
        item = subparsers.add_parser(name)
        item.add_argument("--url", required=True)
        item.add_argument("--run-dir", required=True)
        item.set_defaults(handler=handler)
        if name in {"metadata", "subtitles"}:
            item.add_argument("--timeout", type=int, default=180)
        if name == "subtitles":
            item.add_argument("--languages", default="zh-Hans,zh,en")
            item.add_argument("--allow-browser-fallback", action="store_true")
        if name in {"video", "audio"}:
            item.add_argument("--allow-download", action="store_true")
            item.add_argument("--timeout", type=int, default=7200)
        if name == "video":
            item.add_argument(
                "--quality", choices=("720p", "480p", "1080p", "best"), default="720p"
            )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
        emit(result)
        return 0
    except VideoInsightError as exc:
        emit({"status": "BLOCKED", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
