#!/usr/bin/env python3
"""Deterministic contract and report engine for verify-frontend-delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
SKILL_VERSION = "0.1.0"

RISK_ORDER = ("R0", "R1", "R2", "R3", "R4")
RISK_GATES = {
    "R0": ("L0_SOURCE", "L1_IMPACT", "L2_STATIC"),
    "R1": ("L3_UNIT", "L5_BROWSER", "L7_VISUAL"),
    "R2": ("L3_STATE", "L6_REAL_PAGE"),
    "R3": ("L4_CONTRACT", "L4_BUILD", "L6_REAL_BACKEND"),
    "R4": ("L8_UNION_REGRESSION", "L8_INDEPENDENT_REVIEW"),
}

EVIDENCE_ORDER = (
    "STATIC_VERIFIED",
    "UNIT_VERIFIED",
    "BROWSER_FIXTURE_VERIFIED",
    "UI_PATH_VERIFIED_WITH_SYNTHETIC_DATA",
    "REAL_BACKEND_INTEGRATION_VERIFIED",
    "REAL_PAGE_E2E_ACCEPTED",
)
EVIDENCE_RANK = {name: rank for rank, name in enumerate(EVIDENCE_ORDER, start=1)}
GATE_MIN_EVIDENCE = {
    "L0_SOURCE": "STATIC_VERIFIED",
    "L1_IMPACT": "STATIC_VERIFIED",
    "L2_STATIC": "STATIC_VERIFIED",
    "L3_UNIT": "UNIT_VERIFIED",
    "L3_STATE": "UNIT_VERIFIED",
    "L4_CONTRACT": "UNIT_VERIFIED",
    "L4_BUILD": "STATIC_VERIFIED",
    "L5_BROWSER": "BROWSER_FIXTURE_VERIFIED",
    "L6_REAL_PAGE": "UI_PATH_VERIFIED_WITH_SYNTHETIC_DATA",
    "L6_REAL_BACKEND": "REAL_BACKEND_INTEGRATION_VERIFIED",
    "L7_VISUAL": "UI_PATH_VERIFIED_WITH_SYNTHETIC_DATA",
    "L8_UNION_REGRESSION": "BROWSER_FIXTURE_VERIFIED",
    "L8_INDEPENDENT_REVIEW": "STATIC_VERIFIED",
}

CONTRACT_STATES = {"DRAFT", "FROZEN", "LATE_CONTRACT_RECONSTRUCTION"}
GATE_STATUSES = {
    "PASS",
    "FAIL",
    "BLOCKED_BY_ENVIRONMENT",
    "TIMEOUT",
    "NOT_RUN",
    "WAIVED_BASELINE",
}
WAIVER_ELIGIBLE_GATES = {"L2_STATIC", "L4_BUILD"}


class GateError(RuntimeError):
    """Raised for deterministic validation failures."""


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    kind: str
    authority_scope: str
    path: str


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"无法读取 JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"JSON 顶层必须是对象: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def run_git(repo: Path, args: Iterable[str], *, binary: bool = False) -> str | bytes:
    command = ["git", "-C", str(repo), *args]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise GateError(f"Git 命令失败 ({' '.join(command)}): {message}")
    if binary:
        return result.stdout
    return result.stdout.decode("utf-8", errors="replace").strip()


def resolve_repo(repo: Path) -> Path:
    root = run_git(repo.resolve(), ["rev-parse", "--show-toplevel"])
    assert isinstance(root, str)
    return Path(root).resolve()


def repository_snapshot(
    repo: Path, base_ref: str, head_ref: str | None = None
) -> dict[str, Any]:
    root = resolve_repo(repo)
    resolved_head_ref = head_ref or "HEAD"
    head = run_git(root, ["rev-parse", resolved_head_ref])
    base_commit = run_git(root, ["rev-parse", base_ref])
    branch = run_git(root, ["branch", "--show-current"])
    if head_ref is None:
        target_kind = "WORKTREE"
        status = run_git(root, ["status", "--short", "--untracked-files=all"])
        changed = run_git(root, ["diff", "--name-status", str(base_commit)])
        diff = run_git(root, ["diff", "--binary", str(base_commit)], binary=True)
    else:
        target_kind = "GIT_REF"
        status = ""
        changed = run_git(root, ["diff", "--name-status", str(base_commit), str(head)])
        diff = run_git(
            root, ["diff", "--binary", str(base_commit), str(head)], binary=True
        )
    assert isinstance(head, str)
    assert isinstance(base_commit, str)
    assert isinstance(branch, str)
    assert isinstance(status, str)
    assert isinstance(changed, str)
    assert isinstance(diff, bytes)
    changed_files = [line for line in changed.splitlines() if line]
    for line in status.splitlines():
        if line.startswith("?? ") and line[3:] not in changed_files:
            changed_files.append(f"??\t{line[3:]}")
    return {
        "root": str(root),
        "branch": branch,
        "base_ref": base_ref,
        "base_commit": base_commit,
        "head_ref": resolved_head_ref,
        "head": head,
        "target_kind": target_kind,
        "dirty": bool(status),
        "status_lines": status.splitlines() if status else [],
        "changed_files": changed_files,
        "diff_sha256": sha256_bytes(diff + status.encode("utf-8")),
        "captured_at": utc_now(),
    }


def current_repository_snapshot(contract: dict[str, Any]) -> dict[str, Any]:
    original = contract["repository"]
    head_ref = (
        original.get("head_ref") if original.get("target_kind") == "GIT_REF" else None
    )
    return repository_snapshot(
        Path(original["root"]), str(original["base_ref"]), head_ref
    )


def repository_drift(
    contract: dict[str, Any], current: dict[str, Any]
) -> list[dict[str, Any]]:
    original = contract["repository"]
    fields = (
        "root",
        "base_commit",
        "head",
        "target_kind",
        "dirty",
        "status_lines",
        "changed_files",
        "diff_sha256",
    )
    return [
        {"field": field, "before": original.get(field), "after": current.get(field)}
        for field in fields
        if original.get(field) != current.get(field)
    ]


def hash_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        if ".git" in child.parts:
            continue
        relative = child.relative_to(path).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def path_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def fingerprint_source(repo: Path, source: SourceSpec) -> dict[str, Any]:
    candidate = Path(source.path).expanduser()
    if not candidate.is_absolute():
        candidate = repo / candidate
    resolved = candidate.resolve()
    record: dict[str, Any] = {
        "id": source.source_id,
        "kind": source.kind,
        "authority_scope": source.authority_scope,
        "path": str(resolved),
        "exists": resolved.exists(),
        "sha256": None,
        "git_blob": None,
    }
    if not resolved.exists():
        return record
    record["entry_type"] = "directory" if resolved.is_dir() else "file"
    record["sha256"] = (
        hash_directory(resolved)
        if resolved.is_dir()
        else sha256_bytes(resolved.read_bytes())
    )
    if resolved.is_file() and path_within(resolved, repo):
        relative = resolved.relative_to(repo).as_posix()
        tracked = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--error-unmatch", relative],
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0:
            blob = run_git(repo, ["hash-object", relative])
            assert isinstance(blob, str)
            record["git_blob"] = blob
            record["repo_relative_path"] = relative
    return record


def parse_source(value: str) -> SourceSpec:
    parts = value.split("::", 3)
    if len(parts) != 4 or any(not part.strip() for part in parts):
        raise argparse.ArgumentTypeError(
            "source 必须是 ID::KIND::AUTHORITY_SCOPE::PATH"
        )
    return SourceSpec(*(part.strip() for part in parts))


def required_gates(risk_level: str) -> list[str]:
    if risk_level not in RISK_ORDER:
        raise GateError(f"未知风险等级: {risk_level}")
    gates: list[str] = []
    for risk in RISK_ORDER[: RISK_ORDER.index(risk_level) + 1]:
        gates.extend(RISK_GATES[risk])
    return gates


def default_run_root() -> Path:
    return Path.home() / ".local" / "state" / "verify-frontend-delivery" / "runs"


def make_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def contract_payload(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    repo = resolve_repo(Path(args.repo))
    snapshot = repository_snapshot(repo, args.base, getattr(args, "head", None))
    run_id = args.run_id or make_run_id()
    run_root = Path(args.run_root).expanduser().resolve()
    run_dir = run_root / run_id
    sources = [fingerprint_source(repo, source) for source in args.source]
    issue_set = sorted(set(args.issue))
    contract = {
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "contract_id": f"contract-{run_id}",
        "run_id": run_id,
        "state": "DRAFT",
        "created_at": utc_now(),
        "invocation": {"mode": "prepare", "explicit": True},
        "repository": snapshot,
        "source_manifest": sources,
        "traceability": {
            "requested_issue_set": issue_set,
            "confirmed_issue_set": issue_set,
        },
        "scope": {
            "in_scope": [],
            "out_of_scope": [],
            "target_routes": [],
            "target_files": [],
        },
        "risk_level": args.risk,
        "required_gates": required_gates(args.risk),
        "product_contract": {
            "user_visible_change": "",
            "non_goals": [],
            "authority_map": [],
            "conflicts": [],
            "assumptions": [],
            "open_questions": [],
            "acceptance_scenarios": [],
            "lifecycle_matrix": [],
        },
        "waivers": [],
        "approval": {
            "status": "PENDING",
            "approved_by": None,
            "approved_at": None,
        },
    }
    return contract, run_dir


def contract_fingerprint(contract: dict[str, Any]) -> str:
    payload = dict(contract)
    payload.pop("contract_fingerprint", None)
    return sha256_bytes(canonical_json(payload))


def validate_contract(
    contract: dict[str, Any], *, for_freeze: bool = False, for_verify: bool = False
) -> list[str]:
    errors: list[str] = []
    required_keys = {
        "schema_version",
        "skill_version",
        "contract_id",
        "run_id",
        "state",
        "repository",
        "source_manifest",
        "traceability",
        "scope",
        "risk_level",
        "required_gates",
        "product_contract",
        "approval",
    }
    missing = sorted(required_keys - set(contract))
    if missing:
        errors.append(f"contract 缺少字段: {', '.join(missing)}")
        return errors
    if contract["schema_version"] != SCHEMA_VERSION:
        errors.append(
            f"schema_version 不支持: {contract['schema_version']} != {SCHEMA_VERSION}"
        )
    if contract["risk_level"] not in RISK_ORDER:
        errors.append(f"未知风险等级: {contract['risk_level']}")
    if contract["state"] not in CONTRACT_STATES:
        errors.append(f"未知 contract state: {contract['state']}")

    sources = contract.get("source_manifest")
    if not isinstance(sources, list) or not sources:
        errors.append("source_manifest 不能为空")
    else:
        source_ids = [
            source.get("id") for source in sources if isinstance(source, dict)
        ]
        if len(source_ids) != len(set(source_ids)):
            errors.append("source_manifest id 必须唯一")
        for source in sources:
            if not isinstance(source, dict):
                errors.append("source_manifest 条目必须是对象")
                continue
            for key in ("id", "kind", "authority_scope", "path", "exists"):
                if key not in source:
                    errors.append(f"source 缺少字段 {key}: {source}")
            if not source.get("exists"):
                errors.append(
                    f"SOURCE_MISSING: {source.get('id')} {source.get('path')}"
                )

    traceability = contract.get("traceability", {})
    requested = sorted(set(traceability.get("requested_issue_set", [])))
    confirmed = sorted(set(traceability.get("confirmed_issue_set", [])))
    if requested != confirmed:
        errors.append(
            f"ISSUE_SET_MISMATCH: requested={requested}, confirmed={confirmed}"
        )

    if contract.get("risk_level") in RISK_ORDER:
        expected = set(required_gates(contract["risk_level"]))
        actual = set(contract.get("required_gates", []))
        omitted = sorted(expected - actual)
        if omitted:
            errors.append(f"required_gates 缺少风险必跑项: {', '.join(omitted)}")

    if for_freeze or for_verify:
        product = contract.get("product_contract", {})
        if not str(product.get("user_visible_change", "")).strip():
            errors.append("user_visible_change 不能为空")
        if not product.get("authority_map"):
            errors.append("authority_map 不能为空")
        if not product.get("acceptance_scenarios"):
            errors.append("acceptance_scenarios 不能为空")
        if contract.get("risk_level") in {"R2", "R3", "R4"} and not product.get(
            "lifecycle_matrix"
        ):
            errors.append("R2-R4 必须提供 lifecycle_matrix")
        for conflict in product.get("conflicts", []):
            if not isinstance(conflict, dict):
                errors.append("conflict 条目必须是对象")
                continue
            if conflict.get("status") != "RESOLVED" and conflict.get("priority") in {
                "P0",
                "P1",
            }:
                errors.append(
                    f"SOURCE_CONFLICT: {conflict.get('id', 'unknown')} 未解决"
                )

    if for_verify:
        if contract["state"] not in {"FROZEN", "LATE_CONTRACT_RECONSTRUCTION"}:
            errors.append("verify 需要 FROZEN 或 LATE_CONTRACT_RECONSTRUCTION contract")
        approval = contract.get("approval", {})
        if approval.get("status") != "APPROVED" or not approval.get("approved_by"):
            errors.append("contract 未获得用户批准")
        expected_fingerprint = contract.get("contract_fingerprint")
        if not expected_fingerprint:
            errors.append("contract 缺少 contract_fingerprint")
        elif expected_fingerprint != contract_fingerprint(contract):
            errors.append("CONTRACT_CHANGED: contract fingerprint 不匹配")
    return errors


def source_drift(contract: dict[str, Any]) -> list[dict[str, Any]]:
    repo = resolve_repo(Path(contract["repository"]["root"]))
    changes: list[dict[str, Any]] = []
    for original in contract["source_manifest"]:
        source = SourceSpec(
            str(original["id"]),
            str(original["kind"]),
            str(original["authority_scope"]),
            str(original["path"]),
        )
        current = fingerprint_source(repo, source)
        changed_fields = [
            field
            for field in ("exists", "sha256", "git_blob")
            if original.get(field) != current.get(field)
        ]
        if changed_fields:
            changes.append(
                {
                    "id": original["id"],
                    "path": original["path"],
                    "changed_fields": changed_fields,
                    "before": {field: original.get(field) for field in changed_fields},
                    "after": {field: current.get(field) for field in changed_fields},
                }
            )
    return changes


def normalize_finding(finding: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(finding)
    if not normalized.get("fingerprint"):
        identity = {
            key: normalized.get(key)
            for key in ("tool", "file", "line", "code", "message")
        }
        normalized["fingerprint"] = sha256_bytes(canonical_json(identity))
    return normalized


def compare_findings(
    baseline: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    baseline_findings = [
        normalize_finding(item) for item in baseline.get("findings", [])
    ]
    current_findings = [normalize_finding(item) for item in current.get("findings", [])]
    baseline_by_id = {item["fingerprint"]: item for item in baseline_findings}
    current_by_id = {item["fingerprint"]: item for item in current_findings}
    new_ids = sorted(set(current_by_id) - set(baseline_by_id))
    fixed_ids = sorted(set(baseline_by_id) - set(current_by_id))
    unchanged_ids = sorted(set(baseline_by_id) & set(current_by_id))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "FAIL" if new_ids else "PASS",
        "new": [current_by_id[item] for item in new_ids],
        "fixed": [baseline_by_id[item] for item in fixed_ids],
        "unchanged": [current_by_id[item] for item in unchanged_ids],
        "counts": {
            "baseline": len(baseline_findings),
            "current": len(current_findings),
            "new": len(new_ids),
            "fixed": len(fixed_ids),
            "unchanged": len(unchanged_ids),
        },
    }


def waiver_is_approved(
    contract: dict[str, Any], gate_id: str, confirmed_issue_set: list[str]
) -> bool:
    if gate_id not in WAIVER_ELIGIBLE_GATES:
        return False
    now = datetime.now(UTC)
    for waiver in contract.get("waivers", []):
        if waiver.get("gate_id") != gate_id or waiver.get("status") != "APPROVED":
            continue
        if not waiver.get("approved_by"):
            continue
        if sorted(set(waiver.get("issue_set", []))) != confirmed_issue_set:
            continue
        expires_at = waiver.get("expires_at")
        if not expires_at:
            continue
        try:
            expiry = datetime.fromisoformat(expires_at)
        except ValueError:
            continue
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry > now:
            return True
    return False


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Frontend Delivery Gate Report",
        "",
        f"- Final status: `{report['final_status']}`",
        f"- Run: `{report['run_id']}`",
        f"- Contract: `{report['contract_id']}`",
        f"- Risk: `{report['risk_level']}`",
        f"- Repository: `{report['repository']['root']}`",
        f"- Base/Head: `{report['repository']['base_commit']}` / `{report['repository']['head']}`",
        f"- Auditor: `{report['auditor'].get('id', 'unknown')}`",
        "",
        "## Gate results",
        "",
        "| Gate | Required | Status | Evidence | Summary |",
        "|---|---:|---|---|---|",
    ]
    required = set(report["required_gates"])
    for gate in report["gate_results"]:
        summary = str(gate.get("summary", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{gate['id']}` | {'yes' if gate['id'] in required else 'no'} | "
            f"`{gate['status']}` | `{gate.get('evidence_level', '-')}` | {summary} |"
        )
    lines.extend(["", "## Blocking reasons", ""])
    if report["blocking_reasons"]:
        lines.extend(f"- {reason}" for reason in report["blocking_reasons"])
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    if report["warnings"]:
        lines.extend(
            f"- `{warning.get('priority', 'P2')}` {warning.get('message', '')}"
            for warning in report["warnings"]
        )
    else:
        lines.append("- None")
    lines.extend(["", "## Unverified", ""])
    if report["unverified_items"]:
        lines.extend(f"- {item}" for item in report["unverified_items"])
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def finalize_report(
    contract: dict[str, Any], results: dict[str, Any]
) -> dict[str, Any]:
    contract_errors = validate_contract(contract, for_verify=True)
    drift = source_drift(contract) if not contract_errors else []
    fatal_blockers = list(contract_errors)
    incomplete_blockers: list[str] = []
    if drift:
        fatal_blockers.append(f"SOURCE_CHANGED: {len(drift)} source(s) drifted")
    current_repo = current_repository_snapshot(contract)
    repo_drift = repository_drift(contract, current_repo)
    if repo_drift:
        fatal_blockers.append(f"REPOSITORY_CHANGED: {len(repo_drift)} field(s) drifted")

    auditor = results.get("auditor", {})
    if not auditor.get("independent_context"):
        fatal_blockers.append("INDEPENDENT_AUDITOR_UNAVAILABLE")

    confirmed_issue_set = sorted(
        set(contract["traceability"].get("confirmed_issue_set", []))
    )
    result_issue_set = sorted(set(results.get("issue_set", [])))
    if result_issue_set != confirmed_issue_set:
        fatal_blockers.append(
            f"ISSUE_SET_MISMATCH: contract={confirmed_issue_set}, results={result_issue_set}"
        )

    gates = results.get("gates", [])
    if not isinstance(gates, list):
        fatal_blockers.append("gates 必须是数组")
        gates = []
    gate_by_id: dict[str, dict[str, Any]] = {}
    for gate in gates:
        if not isinstance(gate, dict) or not gate.get("id"):
            fatal_blockers.append(f"无效 gate result: {gate}")
            continue
        gate_id = str(gate["id"])
        if gate_id in gate_by_id:
            fatal_blockers.append(f"重复 gate result: {gate_id}")
            continue
        gate_by_id[gate_id] = gate

    required = required_gates(contract["risk_level"])
    for gate_id in contract.get("required_gates", []):
        if gate_id not in required:
            required.append(gate_id)

    failed: list[str] = []
    for gate_id in required:
        gate = gate_by_id.get(gate_id)
        if gate is None:
            incomplete_blockers.append(f"MISSING_REQUIRED_GATE: {gate_id}")
            continue
        status = gate.get("status")
        if status not in GATE_STATUSES:
            fatal_blockers.append(f"INVALID_GATE_STATUS: {gate_id}={status}")
            continue
        if status == "FAIL":
            failed.append(f"REQUIRED_GATE_FAILED: {gate_id}")
            continue
        if status in {"BLOCKED_BY_ENVIRONMENT", "TIMEOUT", "NOT_RUN"}:
            incomplete_blockers.append(f"REQUIRED_GATE_{status}: {gate_id}")
            continue
        if status == "WAIVED_BASELINE":
            if not waiver_is_approved(contract, gate_id, confirmed_issue_set):
                fatal_blockers.append(f"UNAPPROVED_WAIVER: {gate_id}")
            continue
        minimum = GATE_MIN_EVIDENCE.get(gate_id, "STATIC_VERIFIED")
        evidence = gate.get("evidence_level")
        if evidence not in EVIDENCE_RANK:
            incomplete_blockers.append(f"INVALID_EVIDENCE_LEVEL: {gate_id}={evidence}")
        elif EVIDENCE_RANK[evidence] < EVIDENCE_RANK[minimum]:
            incomplete_blockers.append(
                f"INSUFFICIENT_EVIDENCE: {gate_id} requires {minimum}, got {evidence}"
            )

    warnings = results.get("warnings", [])
    if not isinstance(warnings, list):
        fatal_blockers.append("warnings 必须是数组")
        warnings = []
    high_warnings = [
        warning
        for warning in warnings
        if isinstance(warning, dict) and warning.get("priority") in {"P0", "P1"}
    ]
    failed.extend(
        f"UNRESOLVED_{warning.get('priority')}: {warning.get('message', '')}"
        for warning in high_warnings
    )

    if fatal_blockers:
        final_status = "BLOCKED"
    elif failed:
        final_status = "FAIL"
    elif incomplete_blockers:
        final_status = "BLOCKED"
    elif warnings:
        final_status = "PASS_WITH_P2_WARNINGS"
    else:
        final_status = "PASS"

    unverified = list(results.get("unverified_items", []))
    for gate in gates:
        unverified.extend(gate.get("unverified", []))
    report = {
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "generated_at": utc_now(),
        "run_id": results.get("run_id", contract["run_id"]),
        "contract_id": contract["contract_id"],
        "contract_fingerprint": contract.get("contract_fingerprint"),
        "contract_state": contract["state"],
        "repository": current_repo,
        "contract_repository": contract["repository"],
        "repository_drift": repo_drift,
        "traceability": contract["traceability"],
        "risk_level": contract["risk_level"],
        "required_gates": required,
        "auditor": auditor,
        "source_drift": drift,
        "gate_results": gates,
        "baseline_delta": results.get("baseline_delta"),
        "waivers": contract.get("waivers", []),
        "warnings": warnings,
        "unverified_items": sorted({str(item) for item in unverified}),
        "blocking_reasons": fatal_blockers + incomplete_blockers + failed,
        "artifact_index": results.get("artifact_index", []),
        "timings": results.get("timings", {}),
        "final_status": final_status,
    }
    return report


def command_prepare(args: argparse.Namespace) -> int:
    contract, run_dir = contract_payload(args)
    contract_path = run_dir / "task-contract.draft.json"
    snapshot_path = run_dir / "repository-snapshot.prepare.json"
    write_json(contract_path, contract)
    write_json(snapshot_path, contract["repository"])
    print(
        json.dumps(
            {
                "run_id": contract["run_id"],
                "run_dir": str(run_dir),
                "contract": str(contract_path),
                "snapshot": str(snapshot_path),
                "missing_sources": [
                    source["id"]
                    for source in contract["source_manifest"]
                    if not source["exists"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_validate(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.contract))
    errors = validate_contract(
        contract, for_freeze=args.for_freeze, for_verify=args.for_verify
    )
    print(
        json.dumps(
            {"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2
        )
    )
    return 0 if not errors else 1


def command_freeze(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.contract))
    contract["state"] = (
        "LATE_CONTRACT_RECONSTRUCTION" if args.late_reconstruction else "FROZEN"
    )
    contract["approval"] = {
        "status": "APPROVED",
        "approved_by": args.approved_by,
        "approved_at": utc_now(),
    }
    contract["frozen_at"] = utc_now()
    errors = validate_contract(contract, for_freeze=True)
    if errors:
        raise GateError("无法冻结 contract:\n- " + "\n- ".join(errors))
    contract["contract_fingerprint"] = contract_fingerprint(contract)
    output = Path(args.output).expanduser().resolve()
    if output == Path(args.contract).expanduser().resolve():
        raise GateError("freeze 必须写入独立输出路径，不能覆盖 draft")
    write_json(output, contract)
    print(
        json.dumps(
            {
                "frozen_contract": str(output),
                "contract_fingerprint": contract["contract_fingerprint"],
                "state": contract["state"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_verify_sources(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.contract))
    errors = validate_contract(contract, for_verify=True)
    drift = source_drift(contract) if not errors else []
    result = {"valid_contract": not errors, "errors": errors, "source_drift": drift}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors and not drift else 1


def command_compare_baseline(args: argparse.Namespace) -> int:
    delta = compare_findings(
        load_json(Path(args.baseline)), load_json(Path(args.current))
    )
    if args.output:
        write_json(Path(args.output).expanduser().resolve(), delta)
    print(json.dumps(delta, ensure_ascii=False, indent=2))
    return 0 if delta["status"] == "PASS" else 1


def command_finalize(args: argparse.Namespace) -> int:
    contract = load_json(Path(args.contract))
    results = load_json(Path(args.results))
    report = finalize_report(contract, results)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "gate-report.json"
    markdown_path = output_dir / "gate-report.md"
    write_json(json_path, report)
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "final_status": report["final_status"],
                "gate_report_json": str(json_path),
                "gate_report_markdown": str(markdown_path),
                "blocking_reasons": report["blocking_reasons"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["final_status"] in {"PASS", "PASS_WITH_P2_WARNINGS"} else 1


def command_status(args: argparse.Namespace) -> int:
    report = load_json(Path(args.report))
    gates = report.get("gate_results", [])
    counts: dict[str, int] = {}
    for gate in gates:
        status = str(gate.get("status", "UNKNOWN"))
        counts[status] = counts.get(status, 0) + 1
    summary = {
        "run_id": report.get("run_id"),
        "repository": report.get("repository", {}).get("root"),
        "risk_level": report.get("risk_level"),
        "final_status": report.get("final_status"),
        "gate_counts": counts,
        "source_drift_count": len(report.get("source_drift", [])),
        "blocking_reasons": report.get("blocking_reasons", []),
        "unverified_items": report.get("unverified_items", []),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic frontend contract and gate-report engine"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare", help="create a draft contract and repo snapshot"
    )
    prepare.add_argument("--repo", required=True)
    prepare.add_argument("--base", required=True)
    prepare.add_argument(
        "--head",
        help="optional immutable historical head; omit to snapshot HEAD plus worktree",
    )
    prepare.add_argument("--risk", choices=RISK_ORDER, default="R0")
    prepare.add_argument("--issue", action="append", default=[])
    prepare.add_argument(
        "--source",
        action="append",
        type=parse_source,
        required=True,
        help="ID::KIND::AUTHORITY_SCOPE::PATH",
    )
    prepare.add_argument("--run-root", default=str(default_run_root()))
    prepare.add_argument("--run-id")
    prepare.set_defaults(func=command_prepare)

    validate = subparsers.add_parser("validate", help="validate a contract")
    validate.add_argument("--contract", required=True)
    validate.add_argument("--for-freeze", action="store_true")
    validate.add_argument("--for-verify", action="store_true")
    validate.set_defaults(func=command_validate)

    freeze = subparsers.add_parser("freeze", help="freeze an approved draft contract")
    freeze.add_argument("--contract", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument("--approved-by", required=True)
    freeze.add_argument("--late-reconstruction", action="store_true")
    freeze.set_defaults(func=command_freeze)

    verify_sources = subparsers.add_parser(
        "verify-sources",
        help="validate a frozen contract and recompute source fingerprints",
    )
    verify_sources.add_argument("--contract", required=True)
    verify_sources.set_defaults(func=command_verify_sources)

    baseline = subparsers.add_parser(
        "compare-baseline", help="compare normalized current findings to a baseline"
    )
    baseline.add_argument("--baseline", required=True)
    baseline.add_argument("--current", required=True)
    baseline.add_argument("--output")
    baseline.set_defaults(func=command_compare_baseline)

    finalize = subparsers.add_parser(
        "finalize", help="calculate final status and generate JSON/Markdown reports"
    )
    finalize.add_argument("--contract", required=True)
    finalize.add_argument("--results", required=True)
    finalize.add_argument("--output-dir", required=True)
    finalize.set_defaults(func=command_finalize)

    status = subparsers.add_parser("status", help="summarize an existing gate report")
    status.add_argument("--report", required=True)
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except GateError as exc:
        print(
            json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
