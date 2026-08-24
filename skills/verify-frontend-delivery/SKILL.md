---
name: verify-frontend-delivery
description: Prepare a source-fingerprinted frontend product contract, or independently verify a frontend change against PRDs, prototypes, API contracts, repository rules, lifecycle invariants, browser behavior, visual evidence, and baseline deltas. Use only when the user explicitly invokes `$verify-frontend-delivery`, asks to prepare/freeze a frontend delivery contract with this skill, requests an independent frontend regression gate, or asks for this skill's gate status; never select it implicitly for ordinary frontend work.
---

# Verify Frontend Delivery

Turn product intent into a frozen delivery contract, then prevent code-local tests from masquerading as product acceptance. Keep product decisions human-owned and make final gate status deterministic.

## Select one mode

Honor the user's explicit mode:

- `prepare`: discover sources, build the task contract, classify risk, and stop for approval before freezing it. Do not modify product code.
- `verify`: consume a frozen contract and audit the current change with a fresh independent context. Do not implement fixes, commit, push, update JIRA, approve waivers, or update visual baselines.
- `status`: read existing local run artifacts and report source drift, completed gates, blockers, and resumable work. Do not rerun gates unless asked.

If the user explicitly invokes the skill without a mode, infer `status` for a status question, `prepare` before implementation, and `verify` for an existing diff. State the selected mode. Ordinary frontend requests do not invoke this skill.

## Discover the repository protocol

Before every mode:

1. Read all applicable `AGENTS.md`, mandatory generation rules, design-system rules, repository maps, build/test guidance, and dirty-worktree state.
2. Resolve the actual repository root and distinguish similarly named checkouts. Never reuse contracts, baselines, or PASS evidence across repositories.
3. Locate product sources from real paths. Treat a documented path that does not exist as missing input, not authority.
4. Preserve unrelated work. This skill is read-only toward product repositories unless the user separately authorizes a contract or baseline asset change.

## Run `prepare`

Read [authority-and-contract.md](references/authority-and-contract.md), then:

1. Use `scripts/gate.py prepare` to record repository identity, base/head, source paths, content fingerprints, and a draft contract in a user-visible run directory outside the product repository.
2. Inspect PRDs, prototypes, screenshots, API contracts, code, tests, and runtime evidence. Use a real browser for executable prototypes when available.
3. Fill the draft contract with scope, non-goals, user-visible behavior, authority mapping, conflicts, assumptions, acceptance scenarios, lifecycle matrices, traceability identity sets, risk level, and required gates.
4. Treat business semantics, permissions, persistence, irreversible effects, contract meaning, and source conflicts as human decisions. Do not fill gaps with plausible defaults.
5. Present the contract and every blocking conflict. Freeze only after explicit user approval by running `scripts/gate.py freeze` to a separate frozen-contract path.
6. Stop. `prepare` never starts implementation.

If `verify` starts without a frozen contract, reconstruct a draft and mark it `LATE_CONTRACT_RECONSTRUCTION`. Require user approval before continuing; never claim the contract was approved before implementation.

## Run `verify`

Read [risk-and-gates.md](references/risk-and-gates.md) and [evidence-and-status.md](references/evidence-and-status.md), then:

1. Validate the frozen contract and recompute every source fingerprint with `scripts/gate.py verify-sources`. Stop with `BLOCKED` on source drift or unresolved authority conflicts.
2. Independently compute the semantic impact map from the diff, imports/callers, routes, API/DTO/schema boundaries, state authority, persistence, tests, locale, UI-kit, and cross-repository contracts. Do not substitute regex or a finite keyword map for semantic analysis.
3. Ensure every affected behavior maps to a regression scenario or an explicit unverified item. Review every changed test expectation against an approved contract assertion.
4. Run every required gate for the contract risk level. Capture exact commands, exit codes, duration, artifacts, environment identity, and evidence level. A timeout or unavailable environment is not a skip.
5. For visible UI, compare prototype and application along the same path and state. Read [visual-and-waivers.md](references/visual-and-waivers.md).
6. Use a fresh Auditor agent when available. Pass raw sources, the frozen contract, repository/diff coordinates, and raw artifacts—not the Builder's conclusions or suspected defects. If independent context is unavailable, record it and let deterministic finalization return `BLOCKED`.
7. Write raw gate results, then use `scripts/gate.py finalize` to calculate the final status. Never hand-edit the generated Markdown conclusion.
8. Report `PASS`, `PASS_WITH_P2_WARNINGS`, `FAIL`, or `BLOCKED`, plus evidence levels, new/fixed/baseline failures, waivers, and unverified boundaries.

Do not implement a discovered fix in the Auditor context. Return findings to the Builder and rerun all affected downstream gates after repair.

## Run `status`

Use `scripts/gate.py status --report <gate-report.json>`. Summarize:

- repository, contract, skill, base/head, and run identity;
- final status and blocking reasons;
- passed, failed, blocked, timed-out, waived, and not-run gates;
- source drift and unverified evidence;
- which checkpoints remain reusable.

Do not describe `BROWSER_FIXTURE_VERIFIED` or synthetic UI evidence as real backend or real-page E2E acceptance.

## Enforce safety and authority

- Require explicit user approval for every waiver and approved visual baseline.
- Default to no writes in production-backed or non-isolated shared environments. A required write journey without a safe environment is `BLOCKED`.
- Keep solution approval, quality PASS, Git commit, and JIRA write as separate permissions.
- Never auto-delete run artifacts. List exact paths and sizes before any user-requested cleanup.
- Never auto-update CI, existing skills, repository rules, contracts, or baselines.
- Never downgrade risk or required evidence to fit a time budget.

## Use deterministic tooling

Run `python3 scripts/gate.py --help` for commands. The script owns:

- repository/source snapshots and fingerprints;
- contract validation and freezing;
- baseline finding deltas;
- traceability identity checks;
- risk-required gate expansion;
- evidence-rank enforcement;
- final JSON/Markdown status generation.

Use model reasoning only for semantic extraction, authority classification, impact analysis, lifecycle scenarios, visual judgment, and waiver proposals. The model cannot override deterministic status.

## Load references only as needed

- Contract preparation or source conflict: [authority-and-contract.md](references/authority-and-contract.md)
- Risk classification or gate selection: [risk-and-gates.md](references/risk-and-gates.md)
- Gate-result recording or final claims: [evidence-and-status.md](references/evidence-and-status.md)
- Visible UI, screenshots, baseline, or waiver: [visual-and-waivers.md](references/visual-and-waivers.md)
- Skill validation or local historical replay: [local-pilot.md](references/local-pilot.md)

## Completion boundary

Complete `prepare` only with a user-approved frozen contract or a clear `BLOCKED` decision packet. Complete `verify` only after deterministic report generation. A missing required gate, insufficient evidence rank, unapproved waiver, source drift, identity mismatch, unsafe environment, or unavailable independent Auditor prevents `PASS`.
