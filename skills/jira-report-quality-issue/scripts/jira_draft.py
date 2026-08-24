#!/usr/bin/env python3
"""Validate and canonicalize evidence-backed JIRA issue drafts."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

from jira_evidence import EvidenceError, inspect_image

SCHEMA_VERSION = 1
DESCRIPTION_FIELDS = (
    ("background", "背景与任务目标"),
    ("actualBehavior", "实际行为"),
    ("expectedBehavior", "预期行为"),
    ("impact", "影响"),
    ("reproductionSteps", "复现步骤"),
    ("evidence", "证据"),
    ("affectedScope", "影响范围与相关代码"),
    ("verification", "已完成的验证"),
    ("limitations", "未验证项或限制"),
    ("suggestedDirection", "建议的修复方向"),
)


class DraftError(ValueError):
    """Raised when a draft cannot be safely canonicalized."""


def _reject_unknown_keys(
    value: dict[str, object], allowed: set[str], field: str
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise DraftError(f"{field} 包含未知字段：{', '.join(unknown)}")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_draft(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise DraftError(f"无法读取 draft JSON：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DraftError("draft 顶层必须是 JSON object。")
    return value


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DraftError(f"{field} 必须是非空字符串。")
    return value.strip()


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, field)


def _string_list(value: object, field: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise DraftError(f"{field} 必须是字符串数组。")
    result = [_required_string(item, f"{field}[]") for item in value]
    if not allow_empty and not result:
        raise DraftError(f"{field} 不能为空。")
    return result


def _review_gate(issue: dict[str, object], field: str) -> dict[str, object]:
    value = issue.get(field)
    if not isinstance(value, dict):
        raise DraftError(f"{field} 必须是 object。")
    _reject_unknown_keys(value, {"approved", "notes"}, field)
    if value.get("approved") is not True:
        raise DraftError(
            f"{field}.approved 必须为 true；语义审查未完成时不能 preflight。"
        )
    notes = _required_string(value.get("notes"), f"{field}.notes")
    return {"approved": True, "notes": notes}


def _normalize_description(value: object, issue_index: int) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DraftError(f"issues[{issue_index}].description 必须是 object。")
    _reject_unknown_keys(
        value,
        {key for key, _ in DESCRIPTION_FIELDS},
        f"issues[{issue_index}].description",
    )
    normalized: dict[str, object] = {}
    for key, _ in DESCRIPTION_FIELDS:
        field = f"issues[{issue_index}].description.{key}"
        raw = value.get(key)
        if key in {
            "reproductionSteps",
            "evidence",
            "affectedScope",
            "verification",
            "limitations",
        }:
            normalized[key] = _string_list(raw, field, allow_empty=key == "limitations")
        else:
            normalized[key] = _required_string(raw, field)
    return normalized


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    characters: list[str] = []
    previous_dash = False
    for character in normalized:
        if character.isascii() and character.isalnum():
            characters.append(character.lower())
            previous_dash = False
        elif characters and not previous_dash:
            characters.append("-")
            previous_dash = True
    slug = "".join(characters).strip("-")
    return slug[:48] or "screenshot"


def _extension(mime_type: str) -> str:
    return {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime_type]


def _normalize_duplicate_review(
    value: object, issue_index: int
) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DraftError(f"issues[{issue_index}].duplicateReview 必须是 object。")
    _reject_unknown_keys(
        value,
        {"candidateDigest", "decision", "existingIssueKey", "justification"},
        f"issues[{issue_index}].duplicateReview",
    )
    decision = _required_string(
        value.get("decision"), f"issues[{issue_index}].duplicateReview.decision"
    )
    allowed = {"no-duplicate", "use-existing", "create-despite-candidate"}
    if decision not in allowed:
        raise DraftError(
            f"duplicateReview.decision 必须是：{', '.join(sorted(allowed))}。"
        )
    candidate_digest = _required_string(
        value.get("candidateDigest"),
        f"issues[{issue_index}].duplicateReview.candidateDigest",
    )
    existing_issue_key = _optional_string(
        value.get("existingIssueKey"),
        f"issues[{issue_index}].duplicateReview.existingIssueKey",
    )
    justification = _required_string(
        value.get("justification"),
        f"issues[{issue_index}].duplicateReview.justification",
    )
    if decision == "use-existing" and existing_issue_key is None:
        raise DraftError("duplicateReview.use-existing 必须提供 existingIssueKey。")
    return {
        "candidateDigest": candidate_digest,
        "decision": decision,
        "existingIssueKey": existing_issue_key,
        "justification": justification,
    }


def canonicalize_draft(
    raw: dict[str, object],
    *,
    default_project_key: str,
    default_issue_type: str,
    default_components: tuple[str, ...] = (),
    default_fix_versions: tuple[str, ...] = (),
    attachment_limit: int | None = None,
) -> dict[str, object]:
    _reject_unknown_keys(
        raw,
        {
            "schemaVersion",
            "context",
            "projectKey",
            "issueType",
            "issues",
            "approvedBatchFingerprint",
            "approvedResumeFingerprint",
        },
        "draft",
    )
    if raw.get("schemaVersion") != SCHEMA_VERSION:
        raise DraftError(f"schemaVersion 必须为 {SCHEMA_VERSION}。")
    context = raw.get("context")
    if not isinstance(context, dict):
        raise DraftError("context 必须是 object。")
    _reject_unknown_keys(context, {"repository", "branch", "commit", "task"}, "context")
    normalized_context = {
        "repository": _required_string(context.get("repository"), "context.repository"),
        "branch": _optional_string(context.get("branch"), "context.branch"),
        "commit": _optional_string(context.get("commit"), "context.commit"),
        "task": _required_string(context.get("task"), "context.task"),
    }
    project_key = _required_string(
        raw.get("projectKey") or default_project_key, "projectKey"
    )
    issue_type = _required_string(
        raw.get("issueType") or default_issue_type, "issueType"
    )
    issues = raw.get("issues")
    if not isinstance(issues, list) or not issues:
        raise DraftError("issues 必须是非空数组。")

    normalized_issues: list[dict[str, object]] = []
    total_attachment_size = 0
    for issue_index, issue_value in enumerate(issues):
        if not isinstance(issue_value, dict):
            raise DraftError(f"issues[{issue_index}] 必须是 object。")
        _reject_unknown_keys(
            issue_value,
            {
                "summary",
                "description",
                "priority",
                "components",
                "environment",
                "fixVersions",
                "labels",
                "customFields",
                "qualityReview",
                "safetyReview",
                "screenshots",
                "duplicateReview",
            },
            f"issues[{issue_index}]",
        )
        summary = _required_string(
            issue_value.get("summary"), f"issues[{issue_index}].summary"
        )
        description = _normalize_description(
            issue_value.get("description"), issue_index
        )
        quality_review = _review_gate(issue_value, "qualityReview")
        safety_review = _review_gate(issue_value, "safetyReview")
        priority = _optional_string(
            issue_value.get("priority"), f"issues[{issue_index}].priority"
        )
        components = _string_list(
            issue_value["components"]
            if "components" in issue_value
            else list(default_components),
            f"issues[{issue_index}].components",
        )
        environment = _optional_string(
            issue_value.get("environment"), f"issues[{issue_index}].environment"
        )
        fix_versions = _string_list(
            issue_value["fixVersions"]
            if "fixVersions" in issue_value
            else list(default_fix_versions),
            f"issues[{issue_index}].fixVersions",
        )
        labels = _string_list(
            issue_value.get("labels", []), f"issues[{issue_index}].labels"
        )
        custom_fields = issue_value.get("customFields", {})
        if not isinstance(custom_fields, dict):
            raise DraftError(f"issues[{issue_index}].customFields 必须是 object。")
        if any(
            not isinstance(key, str) or not key.startswith("customfield_")
            for key in custom_fields
        ):
            raise DraftError("customFields 只能包含 customfield_<id> 键。")
        duplicate_review = _normalize_duplicate_review(
            issue_value.get("duplicateReview"), issue_index
        )

        fingerprint_core = {
            "context": normalized_context,
            "projectKey": project_key,
            "issueType": issue_type,
            "summary": summary,
            "description": description,
            "priority": priority,
            "components": sorted(set(components)),
            "environment": environment,
            "fixVersions": sorted(set(fix_versions)),
            "labels": sorted(set(labels)),
            "customFields": custom_fields,
        }
        core = {
            **fingerprint_core,
            "qualityReview": quality_review,
            "safetyReview": safety_review,
            "duplicateReview": duplicate_review,
        }
        issue_fingerprint = sha256_json(fingerprint_core)

        screenshots = issue_value.get("screenshots", [])
        if not isinstance(screenshots, list):
            raise DraftError(f"issues[{issue_index}].screenshots 必须是数组。")
        normalized_screenshots: list[dict[str, object]] = []
        for screenshot_index, screenshot_value in enumerate(screenshots):
            if not isinstance(screenshot_value, dict):
                raise DraftError(
                    f"issues[{issue_index}].screenshots[{screenshot_index}] 必须是 object。"
                )
            _reject_unknown_keys(
                screenshot_value,
                {"path", "description", "visualReview"},
                f"issues[{issue_index}].screenshots[{screenshot_index}]",
            )
            description_value = _required_string(
                screenshot_value.get("description"),
                f"issues[{issue_index}].screenshots[{screenshot_index}].description",
            )
            visual_review = screenshot_value.get("visualReview")
            if (
                not isinstance(visual_review, dict)
                or visual_review.get("approved") is not True
            ):
                raise DraftError(
                    "每张截图都必须完成 visualReview，并将 approved 设为 true。"
                )
            _reject_unknown_keys(
                visual_review,
                {"approved", "notes"},
                f"issues[{issue_index}].screenshots[{screenshot_index}].visualReview",
            )
            review_notes = _required_string(
                visual_review.get("notes"),
                f"issues[{issue_index}].screenshots[{screenshot_index}].visualReview.notes",
            )
            sequence = screenshot_index + 1
            provisional_name = (
                f"{sequence:02d}-{_slug(description_value)}-{issue_fingerprint[:8]}"
            )
            try:
                evidence = inspect_image(
                    _required_string(
                        screenshot_value.get("path"),
                        f"issues[{issue_index}].screenshots[{screenshot_index}].path",
                    ),
                    provisional_name,
                    description_value,
                )
            except EvidenceError as exc:
                raise DraftError(str(exc)) from exc
            final_name = f"{provisional_name}.{_extension(evidence.mime_type)}"
            evidence_value = evidence.to_dict()
            evidence_value["upload_name"] = final_name
            evidence_value["visualReview"] = {"approved": True, "notes": review_notes}
            if attachment_limit is not None and evidence.size > attachment_limit:
                raise DraftError(
                    f"截图 {final_name} 大小 {evidence.size} bytes 超过 JIRA attachment limit "
                    f"{attachment_limit} bytes。"
                )
            normalized_screenshots.append(evidence_value)
            total_attachment_size += evidence.size

        normalized_issue = dict(core)
        normalized_issue["issueFingerprint"] = issue_fingerprint
        normalized_issue["screenshots"] = normalized_screenshots
        normalized_issues.append(normalized_issue)

    plan_without_batch = {
        "schemaVersion": SCHEMA_VERSION,
        "context": normalized_context,
        "projectKey": project_key,
        "issueType": issue_type,
        "issues": normalized_issues,
    }
    fingerprint_input = json.loads(canonical_json(plan_without_batch))
    for issue in fingerprint_input["issues"]:
        for screenshot in issue["screenshots"]:
            screenshot.pop("path", None)
    batch_fingerprint = sha256_json(fingerprint_input)
    return {
        **plan_without_batch,
        "batchFingerprint": batch_fingerprint,
        "operationId": f"batch-{batch_fingerprint[:16]}",
        "totalAttachmentSize": total_attachment_size,
    }


def _description_lines(issue: dict[str, object]) -> list[str]:
    description = issue["description"]
    if not isinstance(description, dict):
        raise DraftError("canonical description 格式无效。")
    lines: list[str] = []
    for key, title in DESCRIPTION_FIELDS:
        lines.append(f"h2. {title}")
        value = description[key]
        if isinstance(value, list):
            lines.extend(f"* {item}" for item in value) if value else lines.append(
                "* 无"
            )
        else:
            lines.append(str(value))
        lines.append("")
    screenshots = issue.get("screenshots") or []
    lines.append("h2. 计划附件")
    if screenshots:
        for screenshot in screenshots:
            lines.append(f"* {screenshot['upload_name']} - {screenshot['description']}")
    else:
        lines.append("* 无")
    lines.extend(
        (
            "",
            "h2. 自动化来源信息",
            f"* Creation fingerprint: {issue['issueFingerprint']}",
        )
    )
    return lines


def render_server_description(issue: dict[str, object]) -> str:
    return "\n".join(_description_lines(issue)).strip()


def _adf_paragraph(text: str) -> dict[str, object]:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def render_cloud_description(issue: dict[str, object]) -> dict[str, object]:
    description = issue["description"]
    if not isinstance(description, dict):
        raise DraftError("canonical description 格式无效。")
    content: list[dict[str, object]] = []
    for key, title in DESCRIPTION_FIELDS:
        content.append(
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": title}],
            }
        )
        value = description[key]
        if isinstance(value, list):
            items = value or ["无"]
            content.append(
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [_adf_paragraph(str(item))]}
                        for item in items
                    ],
                }
            )
        else:
            content.append(_adf_paragraph(str(value)))
    content.append(
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "计划附件"}],
        }
    )
    screenshots = issue.get("screenshots") or []
    planned = [
        f"{item['upload_name']} - {item['description']}" for item in screenshots
    ] or ["无"]
    content.append(
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [_adf_paragraph(item)]}
                for item in planned
            ],
        }
    )
    content.append(
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "自动化来源信息"}],
        }
    )
    content.append(_adf_paragraph(f"Creation fingerprint: {issue['issueFingerprint']}"))
    return {"type": "doc", "version": 1, "content": content}
