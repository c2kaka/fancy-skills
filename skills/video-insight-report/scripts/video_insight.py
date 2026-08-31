#!/usr/bin/env python3
"""Initialize, normalize, extract, render, and validate video insight reports."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import math
import re
import sys
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote

from image_evidence import inspect_image
from video_common import (
    VideoInsightError,
    atomic_write_bytes,
    atomic_write_json,
    command_path,
    load_json,
    parse_video_target,
    require_command_success,
    resolve_within,
    run_command,
    safe_identifier,
    sha256_file,
)

SCHEMA_VERSION = "1.0"
SKILL_VERSION = "0.1.0"
FINAL_STATES = {"COMPLETE", "INCOMPLETE", "BLOCKED", "FAILED"}
DEPTHS = {"concise", "standard", "deep"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
QUOTE_KINDS = {"subtitle", "transcript", "on_screen_text", "none"}
SOURCE_KINDS = {"spoken", "visual", "metadata", "combined"}
STAGE_NAMES = (
    "metadata",
    "captions",
    "transcription",
    "frames",
    "analysis",
    "render",
    "validation",
)
STAGE_STATES = {"PENDING", "COMPLETE", "SKIPPED", "BLOCKED", "FAILED"}


class PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(value: str) -> str:
    parser = PlainTextParser()
    parser.feed(value)
    return " ".join("".join(parser.parts).replace("\u200b", "").split())


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def emit(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def as_number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise VideoInsightError(f"{label} 必须是数字。")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise VideoInsightError(f"{label} 必须是数字。") from exc
    if not math.isfinite(result):
        raise VideoInsightError(f"{label} 必须是有限数字。")
    return result


def format_time(value: Any) -> str:
    seconds = max(0, int(as_number(value, "时间")))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return (
        f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        if hours
        else f"{minutes:02d}:{seconds:02d}"
    )


def parse_timestamp(value: str) -> float:
    clean = value.strip().replace(",", ".")
    pieces = clean.split(":")
    if len(pieces) not in {2, 3}:
        raise VideoInsightError(f"无法解析字幕时间：{value}")
    try:
        numbers = [float(piece) for piece in pieces]
    except ValueError as exc:
        raise VideoInsightError(f"无法解析字幕时间：{value}") from exc
    return sum(number * (60**index) for index, number in enumerate(reversed(numbers)))


def caption_segments_from_text(text: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\r?\n\s*\r?\n", text.lstrip("\ufeff").strip())
    segments: list[dict[str, Any]] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timestamp_index = next(
            (index for index, line in enumerate(lines) if "-->" in line), None
        )
        if timestamp_index is None:
            continue
        left, right = lines[timestamp_index].split("-->", 1)
        right_timestamp = right.strip().split()[0]
        try:
            start = parse_timestamp(left)
            end = parse_timestamp(right_timestamp)
        except VideoInsightError:
            continue
        content = plain_text(" ".join(lines[timestamp_index + 1 :]))
        if content and start >= 0 and end >= start:
            segments.append(
                {"start_seconds": start, "end_seconds": end, "text": content}
            )
    return segments


def candidate_segment_lists(value: Any) -> list[list[Any]]:
    queue = [value]
    candidates: list[list[Any]] = []
    visited = 0
    while queue and visited < 5000:
        current = queue.pop(0)
        visited += 1
        if isinstance(current, list):
            if current and all(isinstance(item, dict) for item in current):
                candidates.append(current)
            queue.extend(current)
        elif isinstance(current, dict):
            queue.extend(current.values())
    return candidates


def normalize_segment_item(item: dict[str, Any]) -> dict[str, Any] | None:
    start_value = next(
        (
            item[key]
            for key in ("start_seconds", "start", "from", "begin")
            if key in item
        ),
        None,
    )
    end_value = next(
        (item[key] for key in ("end_seconds", "end", "to", "finish") if key in item),
        None,
    )
    text_value = next(
        (
            item[key]
            for key in ("text", "content", "body", "caption")
            if item.get(key) not in (None, "")
        ),
        None,
    )
    if start_value is None or end_value is None or text_value is None:
        return None
    try:
        start = float(start_value)
        end = float(end_value)
    except (TypeError, ValueError):
        return None
    text = plain_text(str(text_value))
    if not text or start < 0 or end < start:
        return None
    result: dict[str, Any] = {"start_seconds": start, "end_seconds": end, "text": text}
    for key in ("avg_logprob", "no_speech_prob", "speaker", "confidence"):
        if key in item:
            result[key] = item[key]
    return result


def caption_segments_from_json(value: Any) -> list[dict[str, Any]]:
    best: list[dict[str, Any]] = []
    for candidate in candidate_segment_lists(value):
        normalized = [
            record
            for item in candidate
            if (record := normalize_segment_item(item)) is not None
        ]
        if len(normalized) > len(best):
            best = normalized
    return best


def deduplicate_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        segments, key=lambda item: (item["start_seconds"], item["end_seconds"])
    )
    result: list[dict[str, Any]] = []
    for segment in ordered:
        if (
            result
            and segment["text"] == result[-1]["text"]
            and segment["start_seconds"] <= result[-1]["end_seconds"] + 0.25
        ):
            result[-1]["end_seconds"] = max(
                result[-1]["end_seconds"], segment["end_seconds"]
            )
            continue
        result.append(segment)
    for index, segment in enumerate(result, start=1):
        segment["id"] = f"segment-{index:05d}"
        segment["start_seconds"] = round(segment["start_seconds"], 3)
        segment["end_seconds"] = round(segment["end_seconds"], 3)
    return result


def normalize(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input).expanduser().resolve()
    if not source.is_file() or source.is_symlink() or source.stat().st_size == 0:
        raise VideoInsightError("字幕输入必须是非空普通文件，且不能是符号链接。")
    if source.suffix.lower() in {".vtt", ".srt", ".txt"}:
        segments = caption_segments_from_text(
            source.read_text(encoding="utf-8", errors="replace")
        )
    elif source.suffix.lower() == ".json":
        segments = caption_segments_from_json(load_json(source))
    else:
        raise VideoInsightError("字幕规范化仅支持 VTT、SRT、TXT 或 JSON。")
    normalized = deduplicate_segments(segments)
    if not normalized:
        raise VideoInsightError("字幕文件中没有可用的非空时间轴片段。")
    output = Path(args.output).expanduser().resolve()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_kind": args.source_kind,
        "language": args.language,
        "segments": normalized,
    }
    atomic_write_json(output, payload)
    return {"status": "READY", "path": str(output), "segments": len(normalized)}


def default_manifest(
    target: Any, questions: list[str], args: argparse.Namespace
) -> dict[str, Any]:
    stages = {name: {"status": "PENDING"} for name in STAGE_NAMES}
    return {
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "status": "INCOMPLETE",
        "source": {
            "platform": target.platform,
            "video_id": target.video_id,
            "url": target.url,
            "title": args.title or "Untitled video",
            "creator": args.creator,
            "duration_seconds": args.duration_seconds,
            "language": args.source_language,
        },
        "request": {
            "questions": questions,
            "depth": args.depth,
            "output_language": args.output_language,
            "external_fact_check": False,
            "cloud_transcription_authorized": False,
            "retain_cache": False,
        },
        "pyramid": {"top": "", "supports": []},
        "chapters": [],
        "evidence": [],
        "first_principles": {
            "problem": "",
            "fundamentals": [],
            "assumptions": [],
            "mechanism": [],
            "boundaries": [],
            "rebuilt_conclusion": "",
            "implications": [],
            "open_questions": [],
        },
        "uncertainties": [],
        "pipeline": {"stages": stages},
        "generation": {"created_at": utc_now(), "updated_at": utc_now(), "tools": {}},
    }


def initialize(args: argparse.Namespace) -> dict[str, Any]:
    target = parse_video_target(args.url)
    questions = [question.strip() for question in args.question if question.strip()]
    if not questions:
        raise VideoInsightError("至少需要一个非空分析问题。")
    question_hash = hashlib.sha256(
        json.dumps(questions, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()[:10]
    folder_name = f"{target.platform}-{target.video_id.lower()}-{question_hash}"
    root = Path(args.output_root).expanduser().resolve() / folder_name
    manifest_path = root / "report.json"
    if manifest_path.exists():
        existing = load_json(manifest_path)
        if (
            existing.get("source", {}).get("url") != target.url
            or existing.get("request", {}).get("questions") != questions
        ):
            raise VideoInsightError("已有运行目录与当前输入不匹配，拒绝覆盖。")
        return {
            "status": existing.get("status"),
            "run_dir": str(root),
            "manifest": str(manifest_path),
            "reused": True,
        }
    (root / "evidence" / "raw").mkdir(parents=True, exist_ok=True)
    (root / "evidence" / "derived").mkdir(parents=True, exist_ok=True)
    manifest = default_manifest(target, questions, args)
    atomic_write_json(manifest_path, manifest)
    return {
        "status": "INCOMPLETE",
        "run_dir": str(root),
        "manifest": str(manifest_path),
        "reused": False,
    }


def probe_duration(video: Path) -> float:
    ffprobe = command_path("ffprobe")
    if not ffprobe:
        raise VideoInsightError("缺少 ffprobe，无法验证视频时长。")
    completed = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video),
        ],
        timeout=120,
    )
    raw = require_command_success(completed, label="视频时长探测")
    try:
        duration = float(json.loads(raw)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise VideoInsightError("ffprobe 没有返回可用视频时长。") from exc
    if duration <= 0:
        raise VideoInsightError("视频时长必须大于零。")
    return duration


def extract_frames(args: argparse.Namespace) -> dict[str, Any]:
    video = Path(args.video).expanduser().resolve()
    if not video.is_file() or video.is_symlink() or video.stat().st_size == 0:
        raise VideoInsightError("抽帧输入必须是非空普通视频文件，且不能是符号链接。")
    ffmpeg = command_path("ffmpeg")
    if not ffmpeg:
        raise VideoInsightError("缺少 ffmpeg，无法提取真实视频帧。")
    plan_raw = load_json(Path(args.plan).expanduser().resolve())
    plan = plan_raw.get("evidence") if isinstance(plan_raw, dict) else plan_raw
    if not isinstance(plan, list) or not plan:
        raise VideoInsightError("截图计划必须是非空数组或包含 evidence 数组的对象。")
    report_dir = Path(args.report_dir).expanduser().resolve()
    raw_dir = report_dir / "evidence" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    duration = probe_duration(video)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(plan, start=1):
        if not isinstance(item, dict):
            raise VideoInsightError(f"第 {index} 个截图计划必须是对象。")
        evidence_id = safe_identifier(
            str(item.get("id") or f"evidence-{index:03d}"), label="证据 ID"
        )
        if evidence_id in seen:
            raise VideoInsightError(f"重复证据 ID：{evidence_id}")
        seen.add(evidence_id)
        timestamp = as_number(
            item.get("time_seconds", item.get("start_seconds")),
            f"{evidence_id} 截图时间",
        )
        if timestamp < 0 or timestamp >= duration:
            raise VideoInsightError(
                f"{evidence_id} 截图时间超出视频范围 0..{duration:.3f}。"
            )
        output = raw_dir / f"{evidence_id}.png"
        completed = run_command(
            [
                ffmpeg,
                "-nostdin",
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-y",
                str(output),
            ],
            timeout=args.timeout,
        )
        require_command_success(completed, label=f"提取帧 {evidence_id}")
        info = inspect_image(output)
        image_record = {"path": output.relative_to(report_dir).as_posix(), **info}
        records.append(
            {
                "id": evidence_id,
                "claim": str(item.get("claim") or ""),
                "start_seconds": as_number(
                    item.get("start_seconds", timestamp), f"{evidence_id} 开始时间"
                ),
                "end_seconds": as_number(
                    item.get("end_seconds", timestamp), f"{evidence_id} 结束时间"
                ),
                "quote": "",
                "quote_kind": "none",
                "planned_quote": str(item.get("quote") or ""),
                "planned_quote_kind": item.get("quote_kind", "none"),
                "speaker": item.get("speaker"),
                "confidence": item.get("confidence", "medium"),
                "raw_image": image_record,
                "derived_image": None,
                "rationale": str(item.get("rationale") or ""),
                "source_kind": item.get("source_kind", "combined"),
                "requested_frame_seconds": round(timestamp, 3),
            }
        )
    output_plan = report_dir / "frame-evidence.json"
    atomic_write_json(
        output_plan,
        {
            "video": {
                "sha256": sha256_file(video),
                "duration_seconds": duration,
            },
            "evidence": records,
        },
    )
    return {
        "status": "READY",
        "path": str(output_plan),
        "frames": len(records),
        "duration_seconds": duration,
    }


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VideoInsightError(f"{label} 必须是对象。")
    return value


def require_text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    text = str(value or "").strip()
    if not allow_empty and not text:
        raise VideoInsightError(f"{label} 不能为空。")
    return text


def validate_image_record(record: Any, report_dir: Path, label: str) -> dict[str, Any]:
    image = require_mapping(record, label)
    relative = Path(require_text(image.get("path"), f"{label}.path"))
    if relative.is_absolute():
        raise VideoInsightError(f"{label}.path 必须相对 report.json。")
    path = resolve_within(relative, report_dir, must_exist=True)
    actual = inspect_image(path)
    for key in ("sha256", "mime_type", "width", "height"):
        if image.get(key) != actual[key]:
            raise VideoInsightError(f"{label}.{key} 与实际图片不匹配。")
    return {"path": relative.as_posix(), **actual}


def validate_manifest(manifest: Any, report_dir: Path) -> dict[str, Any]:
    root = require_mapping(manifest, "report.json")
    if root.get("schema_version") != SCHEMA_VERSION:
        raise VideoInsightError(
            f"不支持的 schema_version：{root.get('schema_version')}"
        )
    status = root.get("status")
    if status not in FINAL_STATES:
        raise VideoInsightError(f"status 必须是 {sorted(FINAL_STATES)} 之一。")
    source = require_mapping(root.get("source"), "source")
    target = parse_video_target(require_text(source.get("url"), "source.url"))
    if source.get("platform") != target.platform:
        raise VideoInsightError("source.platform 与 URL 不一致。")
    require_text(source.get("video_id"), "source.video_id")
    require_text(source.get("title"), "source.title", allow_empty=status != "COMPLETE")

    request = require_mapping(root.get("request"), "request")
    questions = request.get("questions")
    if (
        not isinstance(questions, list)
        or not questions
        or not all(str(item).strip() for item in questions)
    ):
        raise VideoInsightError("request.questions 必须是非空字符串数组。")
    if request.get("depth") not in DEPTHS:
        raise VideoInsightError(f"request.depth 必须是 {sorted(DEPTHS)} 之一。")
    require_text(request.get("output_language"), "request.output_language")

    pyramid = require_mapping(root.get("pyramid"), "pyramid")
    supports = pyramid.get("supports")
    if not isinstance(supports, list):
        raise VideoInsightError("pyramid.supports 必须是数组。")
    chapters = root.get("chapters")
    evidence = root.get("evidence")
    uncertainties = root.get("uncertainties")
    if (
        not isinstance(chapters, list)
        or not isinstance(evidence, list)
        or not isinstance(uncertainties, list)
    ):
        raise VideoInsightError("chapters、evidence、uncertainties 必须是数组。")

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(evidence):
        record = require_mapping(item, f"evidence[{index}]")
        evidence_id = safe_identifier(
            require_text(record.get("id"), f"evidence[{index}].id"), label="证据 ID"
        )
        if evidence_id in evidence_by_id:
            raise VideoInsightError(f"重复证据 ID：{evidence_id}")
        start = as_number(record.get("start_seconds"), f"{evidence_id}.start_seconds")
        end = as_number(record.get("end_seconds"), f"{evidence_id}.end_seconds")
        if start < 0 or end < start:
            raise VideoInsightError(f"{evidence_id} 时间范围无效。")
        if record.get("confidence") not in CONFIDENCE_LEVELS:
            raise VideoInsightError(f"{evidence_id}.confidence 无效。")
        if record.get("quote_kind") not in QUOTE_KINDS:
            raise VideoInsightError(f"{evidence_id}.quote_kind 无效。")
        if record.get("source_kind") not in SOURCE_KINDS:
            raise VideoInsightError(f"{evidence_id}.source_kind 无效。")
        if record.get("raw_image") is not None:
            validate_image_record(
                record["raw_image"], report_dir, f"{evidence_id}.raw_image"
            )
        if record.get("derived_image") is not None:
            validate_image_record(
                record["derived_image"], report_dir, f"{evidence_id}.derived_image"
            )
        evidence_by_id[evidence_id] = record

    for index, support in enumerate(supports):
        item = require_mapping(support, f"pyramid.supports[{index}]")
        require_text(
            item.get("title"),
            f"pyramid.supports[{index}].title",
            allow_empty=status != "COMPLETE",
        )
        ids = item.get("evidence_ids")
        if not isinstance(ids, list):
            raise VideoInsightError(
                f"pyramid.supports[{index}].evidence_ids 必须是数组。"
            )
        unknown = [
            evidence_id for evidence_id in ids if evidence_id not in evidence_by_id
        ]
        if unknown:
            raise VideoInsightError(f"金字塔引用未知证据：{unknown}")
        if status == "COMPLETE":
            if not ids:
                raise VideoInsightError("COMPLETE 的每个支撑观点都必须引用证据。")
            if all(
                evidence_by_id[evidence_id].get("confidence") == "low"
                for evidence_id in ids
            ):
                raise VideoInsightError("低置信度证据不能单独支撑核心观点。")

    principles = require_mapping(root.get("first_principles"), "first_principles")
    for key in (
        "fundamentals",
        "assumptions",
        "mechanism",
        "boundaries",
        "implications",
        "open_questions",
    ):
        if not isinstance(principles.get(key), list):
            raise VideoInsightError(f"first_principles.{key} 必须是数组。")
    pipeline = require_mapping(root.get("pipeline"), "pipeline")
    stages = require_mapping(pipeline.get("stages"), "pipeline.stages")
    for name in STAGE_NAMES:
        stage = require_mapping(stages.get(name), f"pipeline.stages.{name}")
        if stage.get("status") not in STAGE_STATES:
            raise VideoInsightError(f"pipeline.stages.{name}.status 无效。")

    if status == "COMPLETE":
        for name in ("metadata", "frames", "analysis"):
            if stages[name].get("status") != "COMPLETE":
                raise VideoInsightError(
                    f"COMPLETE 需要 pipeline.stages.{name}.status 为 COMPLETE。"
                )
        for name in ("captions", "transcription"):
            if stages[name].get("status") not in {"COMPLETE", "SKIPPED"}:
                raise VideoInsightError(
                    f"COMPLETE 需要 pipeline.stages.{name} 明确完成或跳过。"
                )
        for name in ("render", "validation"):
            if stages[name].get("status") not in {"PENDING", "COMPLETE"}:
                raise VideoInsightError(
                    f"COMPLETE 的 pipeline.stages.{name} 不能阻塞或失败。"
                )
        require_text(pyramid.get("top"), "pyramid.top")
        if not supports or not chapters or not evidence:
            raise VideoInsightError("COMPLETE 需要支撑观点、章节地图和真实证据。")
        if any(item.get("raw_image") is None for item in evidence_by_id.values()):
            raise VideoInsightError("COMPLETE 的每条核心证据都需要真实原始帧。")
        require_text(principles.get("problem"), "first_principles.problem")
        require_text(
            principles.get("rebuilt_conclusion"), "first_principles.rebuilt_conclusion"
        )
        for key in ("fundamentals", "assumptions", "mechanism", "boundaries"):
            if not principles[key]:
                raise VideoInsightError(f"COMPLETE 需要 first_principles.{key}。")
        if source.get("platform") == "bilibili" and not evidence_by_id:
            raise VideoInsightError("Bilibili COMPLETE 至少需要一张可验证真实帧。")
    return root


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def interface_labels(language: str, overrides: Any) -> dict[str, str]:
    labels = {
        "report_name": "Video Insight Report",
        "pending": "The report is not complete yet.",
        "unknown_creator": "Unknown creator",
        "question": "Question",
        "open_source": "Open the source video",
        "pyramid_eyebrow": "01 · Pyramid",
        "pyramid": "Pyramid summary",
        "context_eyebrow": "02 · Context",
        "chapters": "Chapter map",
        "traceability_eyebrow": "03 · Traceability",
        "evidence": "Evidence-linked understanding",
        "reconstruction_eyebrow": "04 · Reconstruction",
        "first_principles": "First-principles analysis",
        "limits_eyebrow": "05 · Limits",
        "uncertainties": "Uncertainties and disagreements",
        "provenance_eyebrow": "06 · Provenance",
        "method": "Method and status",
        "contents": "Contents",
        "short_evidence": "Evidence",
        "short_principles": "First principles",
        "short_uncertainties": "Uncertainties",
        "no_content": "No supported content.",
        "no_supports": "No support points available.",
        "no_chapters": "No chapter map available.",
        "no_evidence": "No verified frame evidence available.",
        "no_uncertainties": "No uncertainties recorded.",
        "not_available": "Not available.",
        "problem": "The actual problem",
        "fundamentals": "Irreducible facts and constraints",
        "assumptions": "Explicit and hidden assumptions",
        "mechanism": "Mechanism or causal chain",
        "boundaries": "Boundaries, counterexamples, and alternatives",
        "rebuilt": "Rebuilt conclusion",
        "implications": "Transferable implications",
        "open_questions": "Open questions",
        "evidence_id": "Evidence ID",
        "speaker": "Speaker",
        "schema": "Schema",
        "skill": "Skill",
        "updated": "Updated",
        "footer": "Generated locally from a structured evidence manifest. Source content remains untrusted data.",
        "image_alt": "Evidence frame for",
    }
    if language.lower().startswith("zh"):
        labels.update(
            {
                "report_name": "视频洞察报告",
                "pending": "报告尚未完整生成。",
                "unknown_creator": "未知创作者",
                "question": "分析问题",
                "open_source": "打开原视频",
                "pyramid_eyebrow": "01 · 金字塔",
                "pyramid": "金字塔总结",
                "context_eyebrow": "02 · 上下文",
                "chapters": "视频章节地图",
                "traceability_eyebrow": "03 · 可追溯证据",
                "evidence": "图文证据与理解",
                "reconstruction_eyebrow": "04 · 重新推导",
                "first_principles": "第一性原理分析",
                "limits_eyebrow": "05 · 边界",
                "uncertainties": "不确定性与分歧",
                "provenance_eyebrow": "06 · 来源",
                "method": "生成方法与状态",
                "contents": "目录",
                "short_evidence": "图文证据",
                "short_principles": "第一性原理",
                "short_uncertainties": "不确定性",
                "no_content": "没有可支持的内容。",
                "no_supports": "没有可用的支撑观点。",
                "no_chapters": "没有可用的章节地图。",
                "no_evidence": "没有经过验证的真实帧证据。",
                "no_uncertainties": "没有记录不确定性。",
                "not_available": "暂无内容。",
                "problem": "真正需要解决的问题",
                "fundamentals": "不可继续拆解的事实与约束",
                "assumptions": "显式与隐含假设",
                "mechanism": "机制或因果链",
                "boundaries": "边界、反例与替代解释",
                "rebuilt": "重新构建的结论",
                "implications": "可迁移的启示",
                "open_questions": "待验证问题",
                "evidence_id": "证据 ID",
                "speaker": "说话人",
                "updated": "更新时间",
                "footer": "本报告由结构化证据清单在本地生成；来源内容始终按不可信数据处理。",
                "image_alt": "支持以下结论的证据帧：",
            }
        )
    if isinstance(overrides, dict):
        labels.update(
            {
                key: value
                for key, value in overrides.items()
                if key in labels and isinstance(value, str) and value.strip()
            }
        )
    return labels


def render_string_list(items: Any, empty_label: str) -> str:
    if not isinstance(items, list) or not items:
        return f'<p class="empty">{esc(empty_label)}</p>'
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def image_src(image: dict[str, Any], report_dir: Path, self_contained: bool) -> str:
    relative = Path(image["path"])
    path = resolve_within(relative, report_dir, must_exist=True)
    if self_contained:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{image['mime_type']};base64,{encoded}"
    return quote(relative.as_posix())


def build_html(manifest: dict[str, Any], report_dir: Path, self_contained: bool) -> str:
    css_path = Path(__file__).resolve().parent.parent / "assets" / "report.css"
    css = css_path.read_text(encoding="utf-8")
    source = manifest["source"]
    request = manifest["request"]
    pyramid = manifest["pyramid"]
    status = manifest["status"]
    output_language = str(request.get("output_language") or "en")
    labels = interface_labels(output_language, request.get("ui_labels"))
    supports_html = (
        "".join(
            f'<article class="support"><h3>{esc(item.get("title"))}</h3><p>{esc(item.get("summary"))}</p>'
            f'<div class="badges">{"".join(f'<span class="badge">{esc(eid)}</span>' for eid in item.get("evidence_ids", []))}</div></article>'
            for item in pyramid.get("supports", [])
        )
        or f'<p class="empty">{esc(labels["no_supports"])}</p>'
    )
    chapters_html = (
        "".join(
            f'<article class="chapter"><span class="timestamp">{esc(format_time(item.get("start_seconds", 0)))}–{esc(format_time(item.get("end_seconds", 0)))}</span>'
            f"<div><h3>{esc(item.get('title'))}</h3><p>{esc(item.get('summary'))}</p></div></article>"
            for item in manifest.get("chapters", [])
        )
        or f'<p class="empty">{esc(labels["no_chapters"])}</p>'
    )

    evidence_cards: list[str] = []
    for item in manifest.get("evidence", []):
        chosen = item.get("derived_image") or item.get("raw_image")
        media = ""
        if isinstance(chosen, dict):
            media = (
                f'<div class="evidence-media"><img src="{image_src(chosen, report_dir, self_contained)}" '
                f'alt="{esc(labels["image_alt"])} {esc(item.get("claim"))}"></div>'
            )
        quote_html = (
            f'<blockquote class="quote">{esc(item.get("quote"))}</blockquote>'
            if item.get("quote")
            else ""
        )
        evidence_cards.append(
            f'<article class="evidence-card">{media}<div class="evidence-copy"><div class="badges">'
            f'<span class="timestamp">{esc(format_time(item.get("start_seconds", 0)))}–{esc(format_time(item.get("end_seconds", 0)))}</span>'
            f'<span class="badge">{esc(item.get("confidence"))}</span><span class="badge">{esc(item.get("source_kind"))}</span></div>'
            f"<h3>{esc(item.get('claim'))}</h3>{quote_html}<p>{esc(item.get('rationale'))}</p>"
            f'<p class="provenance">{esc(labels["evidence_id"])}: {esc(item.get("id"))}'
            f"{' · ' + esc(labels['speaker']) + ': ' + esc(item.get('speaker')) if item.get('speaker') else ''}</p></div></article>"
        )
    evidence_html = (
        "".join(evidence_cards) or f'<p class="empty">{esc(labels["no_evidence"])}</p>'
    )

    principles = manifest["first_principles"]
    principle_sections = [
        (labels["problem"], esc(principles.get("problem"))),
        (
            labels["fundamentals"],
            render_string_list(principles.get("fundamentals"), labels["no_content"]),
        ),
        (
            labels["assumptions"],
            render_string_list(principles.get("assumptions"), labels["no_content"]),
        ),
        (
            labels["mechanism"],
            render_string_list(principles.get("mechanism"), labels["no_content"]),
        ),
        (
            labels["boundaries"],
            render_string_list(principles.get("boundaries"), labels["no_content"]),
        ),
        (labels["rebuilt"], esc(principles.get("rebuilt_conclusion"))),
        (
            labels["implications"],
            render_string_list(principles.get("implications"), labels["no_content"]),
        ),
        (
            labels["open_questions"],
            render_string_list(principles.get("open_questions"), labels["no_content"]),
        ),
    ]
    principles_html = "".join(
        f'<article class="principle"><h3>{esc(label)}</h3><div>{content or f'<p class="empty">{esc(labels["not_available"])}</p>'}</div></article>'
        for label, content in principle_sections
    )
    uncertainties_html = (
        "".join(
            f'<article class="uncertainty">{esc(item.get("summary") if isinstance(item, dict) else item)}'
            f"{' — ' + esc(item.get('details')) if isinstance(item, dict) and item.get('details') else ''}</article>"
            for item in manifest.get("uncertainties", [])
        )
        or f'<p class="empty">{esc(labels["no_uncertainties"])}</p>'
    )
    stage_html = "".join(
        f'<span class="badge">{esc(name)}: {esc(value.get("status"))}</span>'
        for name, value in manifest.get("pipeline", {}).get("stages", {}).items()
    )
    language = esc(output_language)
    questions = " · ".join(esc(item) for item in request.get("questions", []))
    return f'''<!doctype html>
<html lang="{language}" dir="auto">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>{esc(source.get("title"))} — {esc(labels["report_name"])}</title>
  <style>{css}</style>
</head>
<body>
<div class="shell">
  <header class="hero">
    <div class="eyebrow">{esc(labels["report_name"])}</div>
    <h1>{esc(source.get("title"))}</h1>
    <p class="lede">{esc(pyramid.get("top") or labels["pending"])}</p>
    <div class="badges"><span class="badge status-{status.lower()}">{esc(status)}</span><span class="badge">{esc(source.get("platform"))}</span><span class="badge">{esc(request.get("depth"))}</span></div>
    <div class="meta"><span>{esc(source.get("creator") or labels["unknown_creator"])}</span><span>{esc(format_time(source.get("duration_seconds") or 0))}</span><span>{esc(labels["question"])}: {questions}</span></div>
    <p><a href="{esc(source.get("url"))}" target="_blank" rel="noopener noreferrer">{esc(labels["open_source"])}</a></p>
  </header>
  <div class="layout">
    <main>
      <section id="summary" class="panel"><div class="eyebrow">{esc(labels["pyramid_eyebrow"])}</div><h2>{esc(labels["pyramid"])}</h2><div class="pyramid-top">{esc(pyramid.get("top") or labels["not_available"])}</div><div class="support-grid">{supports_html}</div></section>
      <section id="chapters" class="panel"><div class="eyebrow">{esc(labels["context_eyebrow"])}</div><h2>{esc(labels["chapters"])}</h2>{chapters_html}</section>
      <section id="evidence" class="panel"><div class="eyebrow">{esc(labels["traceability_eyebrow"])}</div><h2>{esc(labels["evidence"])}</h2><div class="evidence-list">{evidence_html}</div></section>
      <section id="principles" class="panel"><div class="eyebrow">{esc(labels["reconstruction_eyebrow"])}</div><h2>{esc(labels["first_principles"])}</h2><div class="principles">{principles_html}</div></section>
      <section id="uncertainties" class="panel"><div class="eyebrow">{esc(labels["limits_eyebrow"])}</div><h2>{esc(labels["uncertainties"])}</h2>{uncertainties_html}</section>
      <section id="method" class="panel"><div class="eyebrow">{esc(labels["provenance_eyebrow"])}</div><h2>{esc(labels["method"])}</h2><div class="badges">{stage_html}</div><p class="provenance">{esc(labels["schema"])} {esc(manifest.get("schema_version"))} · {esc(labels["skill"])} {esc(manifest.get("skill_version"))} · {esc(labels["updated"])} {esc(manifest.get("generation", {}).get("updated_at"))}</p></section>
    </main>
    <nav class="panel toc" aria-label="{esc(labels["contents"])}"><h2>{esc(labels["contents"])}</h2><ol><li><a href="#summary">{esc(labels["pyramid"])}</a></li><li><a href="#chapters">{esc(labels["chapters"])}</a></li><li><a href="#evidence">{esc(labels["short_evidence"])}</a></li><li><a href="#principles">{esc(labels["short_principles"])}</a></li><li><a href="#uncertainties">{esc(labels["short_uncertainties"])}</a></li><li><a href="#method">{esc(labels["method"])}</a></li></ol></nav>
  </div>
  <footer>{esc(labels["footer"])}</footer>
</div>
</body>
</html>
'''


def validate_html_document(path: Path, manifest: dict[str, Any]) -> None:
    if not path.exists() or path.stat().st_size == 0:
        raise VideoInsightError("HTML 报告不存在或为空。")
    content = path.read_text(encoding="utf-8")
    if f">{manifest['status']}<" not in content:
        raise VideoInsightError("HTML 状态与 manifest 不一致。")
    if re.search(
        r"<(?:img|script|link)[^>]+(?:src|href)=[\"']https?://",
        content,
        flags=re.IGNORECASE,
    ):
        raise VideoInsightError("HTML 包含远程图片、脚本或样式依赖。")
    if "<script" in content.lower():
        raise VideoInsightError("离线报告不应包含脚本。")


def render(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).expanduser().resolve()
    report_dir = manifest_path.parent
    manifest = validate_manifest(load_json(manifest_path), report_dir)
    manifest["pipeline"]["stages"]["render"] = {"status": "COMPLETE"}
    manifest["pipeline"]["stages"]["validation"] = {"status": "PENDING"}
    manifest["generation"]["updated_at"] = utc_now()
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else report_dir / "report.html"
    )
    if output.parent != report_dir:
        raise VideoInsightError("report.html 必须写在 report.json 同一目录。")
    content = build_html(manifest, report_dir, args.self_contained).encode("utf-8")
    atomic_write_bytes(output, content)
    validate_html_document(output, manifest)
    atomic_write_json(manifest_path, manifest)
    return {
        "status": manifest["status"],
        "html": str(output),
        "manifest": str(manifest_path),
        "self_contained": args.self_contained,
    }


def validate(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = validate_manifest(load_json(manifest_path), manifest_path.parent)
    html_path = (
        Path(args.html).expanduser().resolve()
        if args.html
        else manifest_path.parent / "report.html"
    )
    validate_html_document(html_path, manifest)
    if manifest["status"] == "COMPLETE":
        stages = manifest["pipeline"]["stages"]
        if stages["render"].get("status") != "COMPLETE":
            raise VideoInsightError(
                "最终 COMPLETE 验证需要 pipeline.stages.render.status 为 COMPLETE。"
            )
    manifest["pipeline"]["stages"]["validation"] = {"status": "COMPLETE"}
    manifest["generation"]["updated_at"] = utc_now()
    atomic_write_json(manifest_path, manifest)
    return {
        "status": manifest["status"],
        "manifest": str(manifest_path),
        "html": str(html_path),
        "evidence_count": len(manifest["evidence"]),
        "chapter_count": len(manifest["chapters"]),
        "valid": True,
    }


def status(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = validate_manifest(load_json(manifest_path), manifest_path.parent)
    return {
        "status": manifest["status"],
        "source": manifest["source"],
        "questions": manifest["request"]["questions"],
        "stages": manifest["pipeline"]["stages"],
        "uncertainties": manifest["uncertainties"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    item = subparsers.add_parser("init")
    item.add_argument("--url", required=True)
    item.add_argument("--question", action="append", required=True)
    item.add_argument("--output-root", default="./video-reports")
    item.add_argument("--depth", choices=sorted(DEPTHS), default="standard")
    item.add_argument("--output-language", default="zh-CN")
    item.add_argument("--source-language")
    item.add_argument("--title")
    item.add_argument("--creator")
    item.add_argument("--duration-seconds", type=float)
    item.set_defaults(handler=initialize)

    item = subparsers.add_parser("normalize")
    item.add_argument("--input", required=True)
    item.add_argument("--output", required=True)
    item.add_argument(
        "--source-kind",
        choices=("subtitle", "automatic_subtitle", "local_asr"),
        required=True,
    )
    item.add_argument("--language")
    item.set_defaults(handler=normalize)

    item = subparsers.add_parser("extract-frames")
    item.add_argument("--video", required=True)
    item.add_argument("--plan", required=True)
    item.add_argument("--report-dir", required=True)
    item.add_argument("--timeout", type=int, default=900)
    item.set_defaults(handler=extract_frames)

    item = subparsers.add_parser("render")
    item.add_argument("--manifest", required=True)
    item.add_argument("--output")
    item.add_argument("--self-contained", action="store_true")
    item.set_defaults(handler=render)

    item = subparsers.add_parser("validate")
    item.add_argument("--manifest", required=True)
    item.add_argument("--html")
    item.set_defaults(handler=validate)

    item = subparsers.add_parser("status")
    item.add_argument("--manifest", required=True)
    item.set_defaults(handler=status)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        emit(args.handler(args))
        return 0
    except VideoInsightError as exc:
        emit({"status": "FAILED", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
