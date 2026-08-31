#!/usr/bin/env python3
"""Run explicitly authorized, local-only MLX Whisper transcription."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from video_common import (
    VideoInsightError,
    atomic_write_json,
    command_path,
    load_json,
    require_command_success,
    run_command,
    sha256_file,
)

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
MLX_WHISPER_PACKAGE = "mlx-whisper==0.4.3"


def huggingface_hub_root() -> Path:
    configured = os.environ.get("HF_HOME")
    base = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".cache" / "huggingface"
    )
    return base / "hub"


def model_cache_path(model: str) -> Path | None:
    direct = Path(model).expanduser()
    if direct.exists():
        return direct.resolve()
    if "/" not in model:
        return None
    return huggingface_hub_root() / f"models--{model.replace('/', '--')}"


def model_is_available(model: str) -> bool:
    path = model_cache_path(model)
    if path is None or not path.exists():
        return False
    if path.is_file():
        return path.stat().st_size > 0
    snapshots = path / "snapshots"
    roots = [
        path,
        *(
            [item for item in snapshots.iterdir() if item.is_dir()]
            if snapshots.exists()
            else []
        ),
    ]
    return any(
        (root / "config.json").exists() and any(root.glob("weights*.npz"))
        for root in roots
    )


def runtime_command() -> tuple[list[str] | None, bool]:
    installed = command_path("mlx_whisper")
    if installed:
        return [installed], True
    uvx = command_path("uvx")
    if uvx:
        return [uvx, "--from", MLX_WHISPER_PACKAGE, "mlx_whisper"], False
    return None, False


def preflight_result(model: str) -> dict[str, Any]:
    command, installed = runtime_command()
    cache_path = model_cache_path(model)
    model_available = model_is_available(model)
    architecture = platform.machine().lower()
    supported_architecture = architecture == "arm64"
    return {
        "status": "READY"
        if command and model_available and supported_architecture
        else "CONFIRMATION_REQUIRED",
        "engine": "mlx-whisper",
        "package": MLX_WHISPER_PACKAGE,
        "model": model,
        "architecture": architecture,
        "supported_architecture": supported_architecture,
        "runtime_installed": installed,
        "uvx_available": bool(command_path("uvx")),
        "model_available": model_available,
        "model_cache_path": str(cache_path) if cache_path else None,
        "download_required": not installed or not model_available,
        "cloud_used": False,
    }


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    return preflight_result(args.model)


def normalize_result(raw: dict[str, Any], model: str, audio: Path) -> dict[str, Any]:
    segments_raw = raw.get("segments")
    if not isinstance(segments_raw, list):
        raise VideoInsightError("MLX Whisper JSON 缺少 segments 数组。")
    segments: list[dict[str, Any]] = []
    for index, item in enumerate(segments_raw):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        try:
            start = float(item.get("start"))
            end = float(item.get("end"))
        except (TypeError, ValueError):
            continue
        if not text or start < 0 or end < start:
            continue
        record: dict[str, Any] = {
            "id": f"asr-{index + 1:05d}",
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "text": text,
            "avg_logprob": item.get("avg_logprob"),
            "no_speech_prob": item.get("no_speech_prob"),
        }
        words = item.get("words")
        if isinstance(words, list):
            record["words"] = [
                {
                    "word": str(word.get("word") or ""),
                    "start_seconds": word.get("start"),
                    "end_seconds": word.get("end"),
                    "probability": word.get("probability"),
                }
                for word in words
                if isinstance(word, dict) and str(word.get("word") or "").strip()
            ]
        segments.append(record)
    if not segments:
        raise VideoInsightError("MLX Whisper 没有生成可用的非空时间轴片段。")
    return {
        "schema_version": "1.0",
        "source_kind": "local_asr",
        "engine": "mlx-whisper",
        "model": model,
        "language": raw.get("language"),
        "audio_sha256": sha256_file(audio),
        "segments": segments,
    }


def transcribe(args: argparse.Namespace) -> dict[str, Any]:
    audio = Path(args.audio).expanduser().resolve()
    if not audio.is_file() or audio.is_symlink() or audio.stat().st_size == 0:
        raise VideoInsightError("转写输入必须是非空普通音频文件，且不能是符号链接。")
    state = preflight_result(args.model)
    if not state["supported_architecture"]:
        raise VideoInsightError("mlx-whisper 基线路径要求 Apple Silicon arm64。")
    command, installed = runtime_command()
    if command is None:
        raise VideoInsightError("缺少 mlx_whisper，且没有 uvx 可用于隔离运行。")
    if (
        not installed or not state["model_available"]
    ) and not args.allow_model_download:
        raise VideoInsightError(
            f"本地转写运行时或模型尚未准备：{args.model}。确认后使用 --allow-model-download。"
        )

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".local-asr-", dir=output.parent))
    try:
        full_command = [
            *command,
            str(audio),
            "--model",
            args.model,
            "--output-name",
            "result",
            "--output-dir",
            str(staging),
            "--output-format",
            "json",
            "--word-timestamps",
            "True",
            "--verbose",
            "False",
        ]
        if args.language:
            full_command.extend(["--language", args.language])
        completed = run_command(full_command, timeout=args.timeout)
        require_command_success(completed, label="本地 MLX Whisper 转写")
        raw_path = staging / "result.json"
        if not raw_path.exists() or raw_path.stat().st_size == 0:
            diagnostic = (completed.stderr or completed.stdout).strip()[-1800:]
            raise VideoInsightError(
                f"MLX Whisper 未生成 JSON；命令可能内部失败：{diagnostic}"
            )
        raw = load_json(raw_path)
        if not isinstance(raw, dict):
            raise VideoInsightError("MLX Whisper JSON 顶层必须是对象。")
        normalized = normalize_result(raw, args.model, audio)
        atomic_write_json(output, normalized)
        return {
            "status": "READY",
            "path": str(output),
            "segments": len(normalized["segments"]),
            "language": normalized.get("language"),
            "model": args.model,
            "cloud_used": False,
        }
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def emit(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("preflight")
    check.add_argument("--model", default=DEFAULT_MODEL)
    check.set_defaults(handler=preflight)

    run = subparsers.add_parser("transcribe")
    run.add_argument("--audio", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--language")
    run.add_argument("--timeout", type=int, default=21600)
    run.add_argument("--allow-model-download", action="store_true")
    run.set_defaults(handler=transcribe)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        emit(args.handler(args))
        return 0
    except VideoInsightError as exc:
        emit({"status": "BLOCKED", "error": str(exc), "cloud_used": False})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
