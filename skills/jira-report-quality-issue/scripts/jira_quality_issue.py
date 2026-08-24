#!/usr/bin/env python3
"""Guarded CLI for evidence-backed JIRA issue creation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jira_api import (
    ApiError,
    ConfigurationError,
    Deployment,
    JiraClient,
    JiraConfig,
    JiraError,
    OutcomeUnknownError,
    build_create_fields,
    denied_permissions,
    load_config,
)
from jira_draft import DraftError, canonicalize_draft, load_draft, sha256_json
from jira_evidence import inspect_image
from jira_state import (
    OperationAlreadyRunningError,
    StateError,
    cleanup_state,
    operation_lock,
    read_state,
    write_state,
)

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = SKILL_DIR / ".env"
DEFAULT_STATE_DIR = SKILL_DIR / ".state"

EXIT_VALIDATION = 2
EXIT_CONFIRMATION = 3
EXIT_CONFLICT = 4
EXIT_API = 5
EXIT_PARTIAL = 6
EXIT_UNKNOWN = 7


class WorkflowFailure(RuntimeError):
    def __init__(
        self,
        status: str,
        message: str,
        exit_code: int,
        *,
        result: dict[str, object] | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.exit_code = exit_code
        self.result = result or {}


def _permission_summary(raw: dict[str, object]) -> dict[str, object]:
    denied, unknown = denied_permissions(raw)
    return {"denied": denied, "unknown": unknown}


def _attachment_limit(meta: dict[str, object]) -> int | None:
    value = meta.get("uploadLimit")
    return value if isinstance(value, int) and value > 0 else None


def _current_identity(
    deployment: Deployment, user: dict[str, object]
) -> dict[str, object]:
    identity_key = "accountId" if deployment.kind == "cloud" else "name"
    return {
        "identityField": identity_key,
        "identity": user.get(identity_key),
        "displayName": user.get("displayName"),
        "active": user.get("active"),
    }


def _candidate_digest(candidates: list[dict[str, object]]) -> str:
    normalized = [
        {
            "key": item.get("key"),
            "summary": item.get("summary"),
            "status": item.get("status"),
            "updated": item.get("updated"),
        }
        for item in candidates
    ]
    return sha256_json(normalized)


def run_preflight(
    raw_draft: dict[str, object],
    config: JiraConfig,
    client: JiraClient,
) -> dict[str, object]:
    deployment = client.detect_deployment()
    current_user = client.current_user(deployment)
    local_plan = canonicalize_draft(
        raw_draft,
        default_project_key=config.project_key,
        default_issue_type=config.issue_type,
        default_components=config.components,
        default_fix_versions=config.fix_versions,
    )
    permission_result = _permission_summary(
        client.permissions(deployment, str(local_plan["projectKey"]))
    )
    attachment_meta = client.attachment_meta(deployment)
    if attachment_meta.get("enabled") is False:
        upload_limit = 0
    else:
        upload_limit = _attachment_limit(attachment_meta)
    plan = canonicalize_draft(
        raw_draft,
        default_project_key=config.project_key,
        default_issue_type=config.issue_type,
        default_components=config.components,
        default_fix_versions=config.fix_versions,
        attachment_limit=upload_limit,
    )
    metadata = client.create_metadata(
        deployment, str(plan["projectKey"]), str(plan["issueType"])
    )
    candidates = client.search_candidates(
        deployment, str(plan["projectKey"]), str(plan["issueType"])
    )
    candidate_digest = _candidate_digest(candidates)

    blockers: list[dict[str, object]] = []
    warnings: list[str] = []
    if permission_result["denied"]:
        blockers.append(
            {"code": "permission_denied", "permissions": permission_result["denied"]}
        )
    if permission_result["unknown"]:
        warnings.append(
            "部分 JIRA 权限无法通过 mypermissions 预先证明，将在执行时验证。"
        )

    issue_results: list[dict[str, object]] = []
    for index, issue in enumerate(plan["issues"]):
        if not isinstance(issue, dict):
            raise DraftError("canonical issue 格式无效。")
        screenshots = issue.get("screenshots") or []
        if screenshots and attachment_meta.get("enabled") is False:
            blockers.append({"code": "attachments_disabled", "issueIndex": index})
        exact_matches = client.search_fingerprint(
            deployment, str(plan["projectKey"]), str(issue["issueFingerprint"])
        )
        mode = "create"
        existing_key: str | None = None
        duplicate_review = issue.get("duplicateReview")
        if len(exact_matches) > 1:
            blockers.append(
                {
                    "code": "fingerprint_ambiguous",
                    "issueIndex": index,
                    "keys": [item.get("key") for item in exact_matches],
                }
            )
        elif len(exact_matches) == 1:
            mode = "verify-existing"
            existing_key = str(exact_matches[0].get("key") or "")
        elif candidates:
            if (
                not isinstance(duplicate_review, dict)
                or duplicate_review.get("candidateDigest") != candidate_digest
            ):
                blockers.append(
                    {
                        "code": "duplicate_review_required",
                        "issueIndex": index,
                        "candidateDigest": candidate_digest,
                    }
                )
            elif duplicate_review.get("decision") == "use-existing":
                candidate_keys = {str(item.get("key")) for item in candidates}
                requested_key = str(duplicate_review.get("existingIssueKey") or "")
                if requested_key not in candidate_keys:
                    blockers.append(
                        {
                            "code": "existing_issue_not_in_candidate_snapshot",
                            "issueIndex": index,
                            "key": requested_key,
                        }
                    )
                else:
                    mode = "use-existing"
                    existing_key = requested_key
        elif (
            isinstance(duplicate_review, dict)
            and duplicate_review.get("candidateDigest") != candidate_digest
        ):
            blockers.append(
                {
                    "code": "duplicate_snapshot_changed",
                    "issueIndex": index,
                    "candidateDigest": candidate_digest,
                }
            )

        create_fields: dict[str, object] | None = None
        if mode in {"create", "verify-existing"}:
            try:
                create_fields = build_create_fields(
                    deployment, issue, current_user, metadata
                )
            except ApiError as exc:
                blockers.append(
                    {
                        "code": "invalid_create_fields",
                        "issueIndex": index,
                        "message": str(exc),
                    }
                )
        elif screenshots:
            warnings.append(
                f"issue[{index}] 选择现有问题单 {existing_key}；本次不会修改该问题单或上传 draft 中的截图。"
            )
        issue_results.append(
            {
                "issueIndex": index,
                "issueFingerprint": issue["issueFingerprint"],
                "mode": mode,
                "existingIssueKey": existing_key,
                "createFields": create_fields,
                "exactFingerprintMatches": [item.get("key") for item in exact_matches],
            }
        )

    return {
        "status": "preflight_ready" if not blockers else "preflight_blocked",
        "ready": not blockers,
        "deployment": {
            "kind": deployment.kind,
            "apiVersion": deployment.api_version,
            "rawType": deployment.raw_type,
        },
        "currentUser": _current_identity(deployment, current_user),
        "permissions": permission_result,
        "attachmentSettings": {
            "enabled": attachment_meta.get("enabled"),
            "uploadLimit": upload_limit,
        },
        "candidateDigest": candidate_digest,
        "duplicateCandidates": candidates,
        "issues": issue_results,
        "blockers": blockers,
        "warnings": warnings,
        "batchFingerprint": plan["batchFingerprint"],
        "operationId": plan["operationId"],
        "canonicalPlan": plan,
        "_runtime": {
            "deployment": deployment,
            "currentUser": current_user,
            "metadata": metadata,
        },
    }


def public_preflight(result: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in result.items() if key != "_runtime"}


def _expected_values(
    deployment: Deployment,
    issue: dict[str, object],
    current_user: dict[str, object],
    create_fields: dict[str, object],
) -> dict[str, object]:
    identity_key = "accountId" if deployment.kind == "cloud" else "name"
    expected = {
        "project": issue["projectKey"],
        "issuetype": issue["issueType"],
        "summary": issue["summary"],
        "description": create_fields["description"],
        "reporter": current_user[identity_key],
        "assignee": current_user[identity_key],
        "priority": issue.get("priority"),
        "components": sorted(issue.get("components") or []),
        "environment": issue.get("environment"),
        "fixVersions": sorted(issue.get("fixVersions") or []),
        "labels": sorted(issue.get("labels") or []),
    }
    custom_fields = issue.get("customFields")
    if isinstance(custom_fields, dict):
        for key, value in custom_fields.items():
            expected[key] = value
    return expected


def _remote_values(
    deployment: Deployment, issue: dict[str, object], custom_fields: list[str]
) -> dict[str, object]:
    fields = issue.get("fields")
    if not isinstance(fields, dict):
        raise ApiError("issue fields 响应格式无效。")
    project = fields.get("project") if isinstance(fields.get("project"), dict) else {}
    issue_type = (
        fields.get("issuetype") if isinstance(fields.get("issuetype"), dict) else {}
    )
    reporter = (
        fields.get("reporter") if isinstance(fields.get("reporter"), dict) else {}
    )
    assignee = (
        fields.get("assignee") if isinstance(fields.get("assignee"), dict) else {}
    )
    priority = (
        fields.get("priority") if isinstance(fields.get("priority"), dict) else None
    )
    identity_key = "accountId" if deployment.kind == "cloud" else "name"
    components = (
        fields.get("components") if isinstance(fields.get("components"), list) else []
    )
    fix_versions = (
        fields.get("fixVersions") if isinstance(fields.get("fixVersions"), list) else []
    )
    values: dict[str, object] = {
        "project": project.get("key"),
        "issuetype": issue_type.get("name"),
        "summary": fields.get("summary"),
        "description": fields.get("description"),
        "reporter": reporter.get(identity_key),
        "assignee": assignee.get(identity_key),
        "priority": priority.get("name") if isinstance(priority, dict) else None,
        "components": sorted(
            str(item.get("name"))
            for item in components
            if isinstance(item, dict) and item.get("name")
        ),
        "environment": fields.get("environment"),
        "fixVersions": sorted(
            str(item.get("name"))
            for item in fix_versions
            if isinstance(item, dict) and item.get("name")
        ),
        "labels": sorted(str(item) for item in fields.get("labels") or []),
    }
    for key in custom_fields:
        values[key] = fields.get(key)
    return values


def _verification_spec(expected: dict[str, object]) -> dict[str, object]:
    return {
        "fieldHashes": {key: sha256_json(value) for key, value in expected.items()},
        "customFields": [key for key in expected if key.startswith("customfield_")],
    }


def _verify_core(
    deployment: Deployment,
    remote_issue: dict[str, object],
    verification_spec: dict[str, object],
) -> list[str]:
    custom_fields = verification_spec.get("customFields")
    expected_hashes = verification_spec.get("fieldHashes")
    if not isinstance(custom_fields, list) or not isinstance(expected_hashes, dict):
        raise StateError("verification spec 格式无效。")
    remote = _remote_values(
        deployment, remote_issue, [str(item) for item in custom_fields]
    )
    return [
        key
        for key, digest in expected_hashes.items()
        if sha256_json(remote.get(key)) != digest
    ]


def _planned_attachments(issue: dict[str, object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for screenshot in issue.get("screenshots") or []:
        result.append(
            {
                "sha256": screenshot["sha256"],
                "size": screenshot["size"],
                "mimeType": screenshot["mime_type"],
                "uploadName": screenshot["upload_name"],
                "status": "pending",
                "attachmentId": None,
            }
        )
    return result


def _matching_attachments(
    remote_issue: dict[str, object], planned: dict[str, object]
) -> list[dict[str, object]]:
    fields = (
        remote_issue.get("fields")
        if isinstance(remote_issue.get("fields"), dict)
        else {}
    )
    attachments = (
        fields.get("attachment") if isinstance(fields.get("attachment"), list) else []
    )
    return [
        item
        for item in attachments
        if isinstance(item, dict)
        and item.get("filename") == planned.get("uploadName")
        and item.get("size") == planned.get("size")
        and item.get("mimeType") == planned.get("mimeType")
    ]


def _initial_state(preflight: dict[str, object]) -> dict[str, object]:
    runtime = preflight["_runtime"]
    plan = preflight["canonicalPlan"]
    if not isinstance(runtime, dict) or not isinstance(plan, dict):
        raise StateError("preflight runtime 格式无效。")
    deployment = runtime["deployment"]
    current_user = runtime["currentUser"]
    issue_preflights = preflight["issues"]
    state_issues: list[dict[str, object]] = []
    for issue, issue_preflight in zip(plan["issues"], issue_preflights, strict=True):
        create_fields = issue_preflight.get("createFields")
        verification = None
        if isinstance(create_fields, dict):
            verification = _verification_spec(
                _expected_values(deployment, issue, current_user, create_fields)
            )
        state_issues.append(
            {
                "issueFingerprint": issue["issueFingerprint"],
                "mode": issue_preflight["mode"],
                "status": "pending",
                "key": issue_preflight.get("existingIssueKey"),
                "verification": verification,
                "attachments": _planned_attachments(issue)
                if issue_preflight["mode"] in {"create", "verify-existing"}
                else [],
            }
        )
    return {
        "schemaVersion": 1,
        "operationId": plan["operationId"],
        "batchFingerprint": plan["batchFingerprint"],
        "payloadDigest": sha256_json(plan),
        "deployment": {
            "kind": deployment.kind,
            "apiVersion": deployment.api_version,
            "rawType": deployment.raw_type,
        },
        "status": "initialized",
        "issues": state_issues,
        "completedSteps": [],
        "failedStep": None,
    }


def _state_result(state: dict[str, object]) -> dict[str, object]:
    return {
        "operationId": state.get("operationId"),
        "status": state.get("status"),
        "batchFingerprint": state.get("batchFingerprint"),
        "issues": state.get("issues"),
        "completedSteps": state.get("completedSteps"),
        "failedStep": state.get("failedStep"),
        "resumePlan": state.get("resumePlan") or [],
        "resumeFingerprint": state.get("resumeFingerprint"),
    }


def _verified_result(
    state: dict[str, object],
    plan: dict[str, object],
    preflight: dict[str, object],
    config: JiraConfig,
) -> dict[str, object]:
    result = _state_result(state)
    current_user = preflight.get("currentUser")
    identity = current_user.get("identity") if isinstance(current_user, dict) else None
    public_issues: list[dict[str, object]] = []
    for plan_issue, state_issue in zip(
        plan.get("issues") or [], state.get("issues") or [], strict=True
    ):
        key = state_issue.get("key")
        mode = state_issue.get("mode")
        public_issues.append(
            {
                "key": key,
                "url": f"{config.base_url}/browse/{key}" if key else None,
                "status": state_issue.get("status"),
                "mode": mode,
                "summary": plan_issue.get("summary"),
                "project": plan_issue.get("projectKey"),
                "issueType": plan_issue.get("issueType"),
                "priority": plan_issue.get("priority"),
                "components": plan_issue.get("components") or [],
                "environment": plan_issue.get("environment"),
                "fixVersions": plan_issue.get("fixVersions") or [],
                "labels": plan_issue.get("labels") or [],
                "reporter": identity if mode != "use-existing" else None,
                "assignee": identity if mode != "use-existing" else None,
                "attachments": state_issue.get("attachments") or [],
                "differences": state_issue.get("differences") or [],
            }
        )
    result["issues"] = public_issues
    return result


def _refresh_resume_metadata(state: dict[str, object]) -> None:
    resume_plan: list[dict[str, object]] = []
    for issue in state.get("issues") or []:
        key = issue.get("key")
        if not key:
            continue
        for attachment in issue.get("attachments") or []:
            if attachment.get("status") == "missing":
                resume_plan.append(
                    {
                        "key": key,
                        "sha256": attachment.get("sha256"),
                        "name": attachment.get("uploadName"),
                        "size": attachment.get("size"),
                        "mimeType": attachment.get("mimeType"),
                    }
                )
    state["resumePlan"] = resume_plan
    state["resumeFingerprint"] = (
        sha256_json(
            {"operationId": state.get("operationId"), "attachments": resume_plan}
        )
        if resume_plan
        else None
    )


def _record_failure(
    state_dir: Path,
    state: dict[str, object],
    status: str,
    step: str,
    message: str,
) -> None:
    state["status"] = status
    state["failedStep"] = {"step": step, "message": message}
    write_state(state_dir, str(state["operationId"]), state)


def _attachment_from_plan(
    plan_issue: dict[str, object], sha256: str
) -> dict[str, object]:
    matches = [
        item
        for item in plan_issue.get("screenshots") or []
        if item.get("sha256") == sha256
    ]
    if len(matches) != 1:
        raise StateError("draft 与 operation state 的截图 SHA-256 不一致。")
    return matches[0]


def apply_new(
    preflight: dict[str, object],
    config: JiraConfig,
    client: JiraClient,
    state_dir: Path,
) -> dict[str, object]:
    if preflight.get("ready") is not True:
        raise WorkflowFailure(
            "preflight_blocked",
            "preflight 存在 blocker。",
            EXIT_VALIDATION,
            result=public_preflight(preflight),
        )
    plan = preflight["canonicalPlan"]
    runtime = preflight["_runtime"]
    operation_id = str(plan["operationId"])
    with operation_lock(state_dir, operation_id):
        state = read_state(state_dir, operation_id)
        if state is not None and state.get("status") == "verified":
            return _verified_result(state, plan, preflight, config)
        if state is not None and state.get("status") != "initialized":
            raise WorkflowFailure(
                "operation_conflict",
                "operation 已存在且不是可安全启动状态；请使用 verify 或受保护的附件恢复。",
                EXIT_CONFLICT,
                result=_state_result(state),
            )
        if state is None:
            state = _initial_state(preflight)
            write_state(state_dir, operation_id, state)
        deployment = runtime["deployment"]
        current_user = runtime["currentUser"]
        metadata = runtime["metadata"]

        for index, (plan_issue, preflight_issue, state_issue) in enumerate(
            zip(plan["issues"], preflight["issues"], state["issues"], strict=True)
        ):
            mode = preflight_issue["mode"]
            if mode in {"verify-existing", "use-existing"}:
                key = str(preflight_issue["existingIssueKey"])
                custom_fields = tuple(
                    (state_issue.get("verification") or {}).get("customFields") or []
                )
                remote = client.get_issue(deployment, key, extra_fields=custom_fields)
                if mode == "verify-existing" and isinstance(
                    state_issue.get("verification"), dict
                ):
                    differences = _verify_core(
                        deployment, remote, state_issue["verification"]
                    )
                    if differences:
                        state_issue["differences"] = differences
                        _record_failure(
                            state_dir,
                            state,
                            "created_but_unverified",
                            f"issue[{index}].verify-existing",
                            f"字段不一致：{', '.join(differences)}",
                        )
                        raise WorkflowFailure(
                            "created_but_unverified",
                            f"字段不一致：{', '.join(differences)}",
                            EXIT_PARTIAL,
                            result=_state_result(state),
                        )
                    for attachment in state_issue["attachments"]:
                        matches = _matching_attachments(remote, attachment)
                        if len(matches) != 1:
                            attachment["status"] = (
                                "attachment_outcome_unknown"
                                if not matches
                                else "attachment_ambiguous"
                            )
                            _record_failure(
                                state_dir,
                                state,
                                str(attachment["status"]),
                                f"issue[{index}].verify-existing-attachment",
                                f"匹配附件数量为 {len(matches)}。",
                            )
                            raise WorkflowFailure(
                                str(attachment["status"]),
                                "既存 fingerprint issue 的附件验证失败。",
                                EXIT_UNKNOWN,
                                result=_state_result(state),
                            )
                        attachment.update(
                            {
                                "status": "metadata_verified",
                                "attachmentId": matches[0].get("id"),
                            }
                        )
                else:
                    state_issue["attachments"] = []
                state_issue.update(
                    {
                        "key": key,
                        "url": f"{config.base_url}/browse/{key}",
                        "status": "verified_existing",
                    }
                )
                state["completedSteps"].append(f"issue[{index}].verify-existing")
                write_state(state_dir, operation_id, state)
                continue

            state_issue["status"] = "creating"
            state["status"] = "running"
            write_state(state_dir, operation_id, state)
            recovered_key: str | None = None
            try:
                response = client.create_issue(
                    deployment, plan_issue, current_user, metadata
                )
            except OutcomeUnknownError as exc:
                try:
                    matches = client.search_fingerprint(
                        deployment,
                        str(plan["projectKey"]),
                        str(plan_issue["issueFingerprint"]),
                    )
                except JiraError as search_exc:
                    message = f"{exc}; fingerprint 回查失败：{search_exc}"
                    _record_failure(
                        state_dir,
                        state,
                        "creation_outcome_unknown",
                        f"issue[{index}].create",
                        message,
                    )
                    raise WorkflowFailure(
                        "creation_outcome_unknown",
                        message,
                        EXIT_UNKNOWN,
                        result=_state_result(state),
                    ) from search_exc
                if len(matches) == 1 and matches[0].get("key"):
                    recovered_key = str(matches[0]["key"])
                    state["completedSteps"].append(
                        f"issue[{index}].create-metadata-recovered:{recovered_key}"
                    )
                else:
                    status = (
                        "creation_outcome_unknown"
                        if not matches
                        else "fingerprint_ambiguous"
                    )
                    _record_failure(
                        state_dir, state, status, f"issue[{index}].create", str(exc)
                    )
                    raise WorkflowFailure(
                        status, str(exc), EXIT_UNKNOWN, result=_state_result(state)
                    ) from exc
            except JiraError as exc:
                _record_failure(
                    state_dir, state, "partial", f"issue[{index}].create", str(exc)
                )
                raise WorkflowFailure(
                    "partial", str(exc), EXIT_PARTIAL, result=_state_result(state)
                ) from exc
            if recovered_key is None and (
                not isinstance(response.data, dict) or not response.data.get("key")
            ):
                _record_failure(
                    state_dir,
                    state,
                    "creation_outcome_unknown",
                    f"issue[{index}].create",
                    "201 响应缺少 issue key。",
                )
                raise WorkflowFailure(
                    "creation_outcome_unknown",
                    "201 响应缺少 issue key。",
                    EXIT_UNKNOWN,
                    result=_state_result(state),
                )
            issue_key = recovered_key or str(response.data["key"])
            state_issue.update(
                {
                    "key": issue_key,
                    "url": f"{config.base_url}/browse/{issue_key}",
                    "status": "created",
                }
            )
            state["completedSteps"].append(f"issue[{index}].create:{issue_key}")
            write_state(state_dir, operation_id, state)
            try:
                custom_fields = tuple(state_issue["verification"]["customFields"])
                remote = client.get_issue(
                    deployment, issue_key, extra_fields=custom_fields
                )
                differences = _verify_core(
                    deployment, remote, state_issue["verification"]
                )
            except JiraError as exc:
                _record_failure(
                    state_dir,
                    state,
                    "created_but_unverified",
                    f"issue[{index}].verify",
                    str(exc),
                )
                raise WorkflowFailure(
                    "created_but_unverified",
                    str(exc),
                    EXIT_PARTIAL,
                    result=_state_result(state),
                ) from exc
            if differences:
                state_issue["differences"] = differences
                _record_failure(
                    state_dir,
                    state,
                    "created_but_unverified",
                    f"issue[{index}].verify",
                    f"字段不一致：{', '.join(differences)}",
                )
                raise WorkflowFailure(
                    "created_but_unverified",
                    f"字段不一致：{', '.join(differences)}",
                    EXIT_PARTIAL,
                    result=_state_result(state),
                )
            state_issue["status"] = "core_verified"
            state["completedSteps"].append(f"issue[{index}].verify-core")
            write_state(state_dir, operation_id, state)

            for attachment_index, attachment_state in enumerate(
                state_issue["attachments"]
            ):
                source = _attachment_from_plan(
                    plan_issue, str(attachment_state["sha256"])
                )
                inspected = inspect_image(
                    str(source["path"]),
                    str(source["upload_name"]),
                    str(source["description"]),
                )
                if inspected.sha256 != attachment_state["sha256"]:
                    _record_failure(
                        state_dir,
                        state,
                        "partial",
                        f"issue[{index}].attachment[{attachment_index}].local-verify",
                        "截图在批准后发生变化。",
                    )
                    raise WorkflowFailure(
                        "partial",
                        "截图在批准后发生变化。",
                        EXIT_PARTIAL,
                        result=_state_result(state),
                    )
                attachment_state["status"] = "uploading"
                write_state(state_dir, operation_id, state)
                try:
                    client.upload_attachment(
                        deployment,
                        issue_key,
                        Path(str(source["path"])),
                        str(source["upload_name"]),
                        str(source["mime_type"]),
                    )
                except OutcomeUnknownError as exc:
                    try:
                        remote = client.get_issue(deployment, issue_key)
                    except JiraError as verify_exc:
                        message = f"{exc}; 附件回查失败：{verify_exc}"
                        attachment_state["status"] = "attachment_outcome_unknown"
                        _record_failure(
                            state_dir,
                            state,
                            "attachment_outcome_unknown",
                            f"issue[{index}].attachment[{attachment_index}].upload",
                            message,
                        )
                        raise WorkflowFailure(
                            "attachment_outcome_unknown",
                            message,
                            EXIT_UNKNOWN,
                            result=_state_result(state),
                        ) from verify_exc
                    matches = _matching_attachments(remote, attachment_state)
                    if len(matches) == 1:
                        attachment_state.update(
                            {
                                "status": "metadata_verified",
                                "attachmentId": matches[0].get("id"),
                            }
                        )
                        state["completedSteps"].append(
                            f"issue[{index}].attachment[{attachment_index}].metadata-recovered"
                        )
                        write_state(state_dir, operation_id, state)
                        continue
                    status = (
                        "attachment_outcome_unknown"
                        if not matches
                        else "attachment_ambiguous"
                    )
                    attachment_state["status"] = status
                    _record_failure(
                        state_dir,
                        state,
                        status,
                        f"issue[{index}].attachment[{attachment_index}].upload",
                        str(exc),
                    )
                    raise WorkflowFailure(
                        status, str(exc), EXIT_UNKNOWN, result=_state_result(state)
                    ) from exc
                except JiraError as exc:
                    attachment_state["status"] = "failed"
                    _record_failure(
                        state_dir,
                        state,
                        "partial",
                        f"issue[{index}].attachment[{attachment_index}].upload",
                        str(exc),
                    )
                    raise WorkflowFailure(
                        "partial", str(exc), EXIT_PARTIAL, result=_state_result(state)
                    ) from exc
                try:
                    remote = client.get_issue(deployment, issue_key)
                except JiraError as exc:
                    attachment_state["status"] = "uploaded_unverified"
                    _record_failure(
                        state_dir,
                        state,
                        "partial",
                        f"issue[{index}].attachment[{attachment_index}].verify",
                        str(exc),
                    )
                    raise WorkflowFailure(
                        "partial",
                        str(exc),
                        EXIT_PARTIAL,
                        result=_state_result(state),
                    ) from exc
                matches = _matching_attachments(remote, attachment_state)
                if len(matches) != 1:
                    status = (
                        "attachment_outcome_unknown"
                        if not matches
                        else "attachment_ambiguous"
                    )
                    attachment_state["status"] = status
                    _record_failure(
                        state_dir,
                        state,
                        status,
                        f"issue[{index}].attachment[{attachment_index}].verify",
                        f"匹配附件数量为 {len(matches)}。",
                    )
                    raise WorkflowFailure(
                        status,
                        f"匹配附件数量为 {len(matches)}。",
                        EXIT_UNKNOWN,
                        result=_state_result(state),
                    )
                attachment_state.update(
                    {
                        "status": "metadata_verified",
                        "attachmentId": matches[0].get("id"),
                    }
                )
                state["completedSteps"].append(
                    f"issue[{index}].attachment[{attachment_index}].verify"
                )
                write_state(state_dir, operation_id, state)
            state_issue["status"] = "verified"
            write_state(state_dir, operation_id, state)

        state["status"] = "verified"
        state["failedStep"] = None
        write_state(state_dir, operation_id, state)
        return _verified_result(state, plan, preflight, config)


def verify_operation(
    config: JiraConfig, client: JiraClient, state_dir: Path, operation_id: str
) -> dict[str, object]:
    with operation_lock(state_dir, operation_id):
        state = read_state(state_dir, operation_id)
        if state is None:
            raise WorkflowFailure(
                "validation_failed", "找不到 operation。", EXIT_VALIDATION
            )
        deployment = client.detect_deployment()
        state_deployment = state.get("deployment")
        if (
            not isinstance(state_deployment, dict)
            or state_deployment.get("kind") != deployment.kind
        ):
            raise WorkflowFailure(
                "operation_conflict",
                "当前 JIRA deployment 与 operation 不一致。",
                EXIT_CONFLICT,
            )
        unresolved = False
        for issue_state in state.get("issues") or []:
            issue_unresolved = False
            key = issue_state.get("key")
            if not key:
                unresolved = True
                continue
            remote = client.get_issue(
                deployment,
                str(key),
                extra_fields=tuple(
                    (issue_state.get("verification") or {}).get("customFields") or []
                ),
            )
            verification = issue_state.get("verification")
            if isinstance(verification, dict):
                differences = _verify_core(deployment, remote, verification)
                issue_state["differences"] = differences
                if differences:
                    issue_state["status"] = "created_but_unverified"
                    issue_unresolved = True
            for attachment in issue_state.get("attachments") or []:
                previous_status = attachment.get("status")
                matches = _matching_attachments(remote, attachment)
                if len(matches) == 1:
                    attachment.update(
                        {
                            "status": "metadata_verified",
                            "attachmentId": matches[0].get("id"),
                        }
                    )
                elif len(matches) == 0:
                    attachment["status"] = (
                        "attachment_outcome_unknown"
                        if previous_status
                        in {
                            "attachment_outcome_unknown",
                            "attachment_ambiguous",
                            "uploaded_unverified",
                            "uploading",
                        }
                        else "missing"
                    )
                    issue_unresolved = True
                else:
                    attachment["status"] = "attachment_ambiguous"
                    issue_unresolved = True
            if not issue_unresolved and issue_state.get("mode") in {
                "create",
                "verify-existing",
            }:
                issue_state["status"] = "verified"
            unresolved = unresolved or issue_unresolved
        state["status"] = "partial" if unresolved else "verified"
        state["failedStep"] = None if not unresolved else state.get("failedStep")
        _refresh_resume_metadata(state)
        write_state(state_dir, operation_id, state)
        return _state_result(state)


def resume_attachments(
    raw_draft: dict[str, object],
    config: JiraConfig,
    client: JiraClient,
    state_dir: Path,
    operation_id: str,
    confirm: str,
) -> dict[str, object]:
    approved = raw_draft.get("approvedResumeFingerprint")
    if not isinstance(approved, str) or approved != confirm:
        raise WorkflowFailure(
            "confirmation_mismatch",
            "resume confirmation 与 draft 不一致。",
            EXIT_CONFIRMATION,
        )
    with operation_lock(state_dir, operation_id):
        state = read_state(state_dir, operation_id)
        if state is None:
            raise WorkflowFailure(
                "validation_failed", "找不到 operation。", EXIT_VALIDATION
            )
        plan = canonicalize_draft(
            raw_draft,
            default_project_key=config.project_key,
            default_issue_type=config.issue_type,
            default_components=config.components,
            default_fix_versions=config.fix_versions,
        )
        if plan["batchFingerprint"] != state.get("batchFingerprint"):
            raise WorkflowFailure(
                "confirmation_mismatch",
                "draft 与原 operation payload 不一致。",
                EXIT_CONFIRMATION,
            )
        deployment = client.detect_deployment()
        resumable: list[dict[str, object]] = []
        for plan_issue, state_issue in zip(
            plan["issues"], state.get("issues") or [], strict=True
        ):
            key = state_issue.get("key")
            if not key:
                continue
            remote = client.get_issue(
                deployment,
                str(key),
                extra_fields=tuple(
                    (state_issue.get("verification") or {}).get("customFields") or []
                ),
            )
            verification = state_issue.get("verification")
            if isinstance(verification, dict) and _verify_core(
                deployment, remote, verification
            ):
                raise WorkflowFailure(
                    "operation_conflict",
                    f"{key} 核心字段已漂移，禁止补传附件。",
                    EXIT_CONFLICT,
                )
            for attachment in state_issue.get("attachments") or []:
                matches = _matching_attachments(remote, attachment)
                if len(matches) == 1:
                    attachment.update(
                        {
                            "status": "metadata_verified",
                            "attachmentId": matches[0].get("id"),
                        }
                    )
                    continue
                if len(matches) > 1:
                    attachment["status"] = "attachment_ambiguous"
                    raise WorkflowFailure(
                        "operation_conflict",
                        f"附件 {attachment.get('uploadName')} 存在多个远端匹配项，禁止补传。",
                        EXIT_CONFLICT,
                    )
                if attachment.get("status") not in {"failed", "missing", "pending"}:
                    raise WorkflowFailure(
                        "operation_conflict",
                        f"附件 {attachment.get('uploadName')} 结果不明确，禁止补传。",
                        EXIT_CONFLICT,
                    )
                source = _attachment_from_plan(plan_issue, str(attachment["sha256"]))
                inspected = inspect_image(
                    str(source["path"]),
                    str(source["upload_name"]),
                    str(source["description"]),
                )
                if inspected.sha256 != attachment["sha256"]:
                    raise WorkflowFailure(
                        "confirmation_mismatch",
                        "本地截图与原批准 hash 不一致。",
                        EXIT_CONFIRMATION,
                    )
                resumable.append({"key": key, "state": attachment, "source": source})
        resume_plan = [
            {
                "key": item["key"],
                "sha256": item["state"]["sha256"],
                "name": item["state"]["uploadName"],
                "size": item["state"]["size"],
                "mimeType": item["state"]["mimeType"],
            }
            for item in resumable
        ]
        resume_fingerprint = sha256_json(
            {"operationId": operation_id, "attachments": resume_plan}
        )
        if resume_fingerprint != confirm:
            raise WorkflowFailure(
                "confirmation_mismatch",
                f"resume payload 已变化；新的 resume fingerprint：{resume_fingerprint}",
                EXIT_CONFIRMATION,
            )
        for item in resumable:
            attachment = item["state"]
            source = item["source"]
            attachment["status"] = "uploading"
            write_state(state_dir, operation_id, state)
            try:
                client.upload_attachment(
                    deployment,
                    str(item["key"]),
                    Path(str(source["path"])),
                    str(source["upload_name"]),
                    str(source["mime_type"]),
                )
            except OutcomeUnknownError as exc:
                try:
                    remote = client.get_issue(deployment, str(item["key"]))
                except JiraError as verify_exc:
                    message = f"{exc}; 附件回查失败：{verify_exc}"
                    attachment["status"] = "attachment_outcome_unknown"
                    _record_failure(
                        state_dir,
                        state,
                        "attachment_outcome_unknown",
                        "resume-attachment",
                        message,
                    )
                    raise WorkflowFailure(
                        "attachment_outcome_unknown",
                        message,
                        EXIT_UNKNOWN,
                        result=_state_result(state),
                    ) from verify_exc
                matches = _matching_attachments(remote, attachment)
                if len(matches) == 1:
                    attachment.update(
                        {
                            "status": "metadata_verified",
                            "attachmentId": matches[0].get("id"),
                        }
                    )
                    write_state(state_dir, operation_id, state)
                    continue
                attachment["status"] = (
                    "attachment_ambiguous" if matches else "attachment_outcome_unknown"
                )
                _record_failure(
                    state_dir,
                    state,
                    str(attachment["status"]),
                    "resume-attachment",
                    str(exc),
                )
                raise WorkflowFailure(
                    str(attachment["status"]),
                    str(exc),
                    EXIT_UNKNOWN,
                    result=_state_result(state),
                ) from exc
            except JiraError as exc:
                attachment["status"] = "failed"
                _record_failure(
                    state_dir, state, "partial", "resume-attachment", str(exc)
                )
                raise WorkflowFailure(
                    "partial", str(exc), EXIT_PARTIAL, result=_state_result(state)
                ) from exc
            try:
                remote = client.get_issue(deployment, str(item["key"]))
            except JiraError as exc:
                attachment["status"] = "uploaded_unverified"
                _record_failure(
                    state_dir, state, "partial", "resume-attachment-verify", str(exc)
                )
                raise WorkflowFailure(
                    "partial", str(exc), EXIT_PARTIAL, result=_state_result(state)
                ) from exc
            matches = _matching_attachments(remote, attachment)
            if len(matches) != 1:
                attachment["status"] = (
                    "attachment_ambiguous" if matches else "attachment_outcome_unknown"
                )
                _record_failure(
                    state_dir,
                    state,
                    str(attachment["status"]),
                    "resume-attachment-verify",
                    f"匹配附件数量为 {len(matches)}。",
                )
                raise WorkflowFailure(
                    str(attachment["status"]),
                    "附件恢复验证失败。",
                    EXIT_UNKNOWN,
                    result=_state_result(state),
                )
            attachment.update(
                {"status": "metadata_verified", "attachmentId": matches[0].get("id")}
            )
            write_state(state_dir, operation_id, state)
        all_complete = True
        for issue_state in state.get("issues") or []:
            if not issue_state.get("key"):
                all_complete = False
                continue
            if any(
                attachment.get("status") != "metadata_verified"
                for attachment in issue_state.get("attachments") or []
            ):
                all_complete = False
            elif issue_state.get("mode") in {"create", "verify-existing"}:
                issue_state["status"] = "verified"
        state["status"] = "verified" if all_complete else "partial"
        state["failedStep"] = None if all_complete else state.get("failedStep")
        _refresh_resume_metadata(state)
        write_state(state_dir, operation_id, state)
        return _state_result(state)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guarded evidence-backed JIRA issue creation"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser(
        "preflight", help="Run read-only validation and render the canonical plan"
    )
    preflight.add_argument("--draft", type=Path, required=True)
    apply_parser = subparsers.add_parser(
        "apply", help="Apply an approved plan or resume approved attachments"
    )
    apply_parser.add_argument("--draft", type=Path, required=True)
    apply_parser.add_argument("--confirm", required=True)
    apply_parser.add_argument("--operation")
    apply_parser.add_argument("--resume-attachments", action="store_true")
    verify = subparsers.add_parser(
        "verify", help="Verify an existing operation without writes"
    )
    verify.add_argument("--operation", required=True)
    cleanup = subparsers.add_parser(
        "cleanup", help="Delete local state for a verified operation"
    )
    cleanup.add_argument("--operation", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "cleanup":
            cleanup_state(DEFAULT_STATE_DIR, args.operation)
            result = {"status": "cleaned", "operationId": args.operation}
        elif args.command == "verify":
            config = load_config(DEFAULT_ENV_PATH)
            result = verify_operation(
                config, JiraClient(config), DEFAULT_STATE_DIR, args.operation
            )
        else:
            raw = load_draft(args.draft)
            if args.command == "apply" and not args.resume_attachments:
                approved = raw.get("approvedBatchFingerprint")
                if not isinstance(approved, str) or approved != args.confirm:
                    raise WorkflowFailure(
                        "confirmation_mismatch",
                        "--confirm 必须与 draft.approvedBatchFingerprint 完全一致。",
                        EXIT_CONFIRMATION,
                    )
            config = load_config(DEFAULT_ENV_PATH)
            client = JiraClient(config)
            if args.command == "preflight":
                result = public_preflight(run_preflight(raw, config, client))
            elif args.resume_attachments:
                if not args.operation:
                    raise WorkflowFailure(
                        "validation_failed",
                        "附件恢复必须提供 --operation。",
                        EXIT_VALIDATION,
                    )
                result = resume_attachments(
                    raw, config, client, DEFAULT_STATE_DIR, args.operation, args.confirm
                )
            elif args.operation:
                raise WorkflowFailure(
                    "validation_failed",
                    "普通 apply 不能提供 --operation。",
                    EXIT_VALIDATION,
                )
            else:
                preflight = run_preflight(raw, config, client)
                if preflight["batchFingerprint"] != args.confirm:
                    raise WorkflowFailure(
                        "confirmation_mismatch",
                        "重新 preflight 后 batch fingerprint 已变化。",
                        EXIT_CONFIRMATION,
                        result=public_preflight(preflight),
                    )
                result = apply_new(preflight, config, client, DEFAULT_STATE_DIR)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except WorkflowFailure as exc:
        output = {"status": exc.status, "message": str(exc), **exc.result}
        print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
        return exc.exit_code
    except OperationAlreadyRunningError as exc:
        print(
            json.dumps(
                {"status": "operation_already_running", "message": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_CONFLICT
    except (ConfigurationError, DraftError, StateError) as exc:
        print(
            json.dumps(
                {"status": "validation_failed", "message": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_VALIDATION
    except ApiError as exc:
        print(
            json.dumps(
                {"status": "api_failed", "message": str(exc), "httpStatus": exc.status},
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_API
    except JiraError as exc:
        print(
            json.dumps(
                {"status": "jira_failed", "message": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_API


if __name__ == "__main__":
    sys.exit(main())
