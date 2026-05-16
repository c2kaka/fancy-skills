---
name: change-risk-review
description: Use when Codex needs to review current git changes for AI-coding risk, summarize behavior changes, affected historical features, protocol/schema changes, golden-test evidence, change diffusion path, architecture constraint violations, verification adequacy, hallucination-risk types, and uncertainty before commit; also use when the user confirms the review and asks Codex to commit, so the commit message includes concrete change categories with review-level signals (low/medium/high) and PR-review-ready details.
---

# Change Risk Review

## Overview

Use this skill as a lightweight safety gate for fast AI-assisted development. It turns a raw git diff into a focused risk review, then, only after user confirmation, helps create a commit message that classifies the change and describes the concrete impact for PR reviewers.

## Workflow

### 1. Inspect Git State First

Use focused git commands before judging the change:

- `git status --short`
- `git diff --stat`
- `git diff -- <focused paths>` for changed source, tests, docs, configs, schemas, and prompts
- `git diff --cached` if files are already staged
- `git log --oneline -n 5` only when recent context helps classify risk

Do not assume unstaged changes are yours. If unrelated files are dirty, isolate the review to files relevant to the user's request and call out unrelated changes briefly.

## Review Output

Lead with risks and evidence, not a generic summary. Cover these seven required questions:

1. What behaviors changed
   - Describe user-visible behavior, agent routing behavior, prompt/LLM behavior, state transitions, persistence behavior, or error-handling behavior that changed.

2. Which existing features may be affected
   - Name likely affected existing flows, especially planner routing, skill routing, session memory, resume/rerun, rollback, streaming, frontend protocol payloads, and golden scenarios.

3. Which protocol fields were added or modified
   - Check JSON payloads, message `additional_kwargs`, session/memory fields, config keys, API parameters, frontend-rendered markdown/custom markup, database fields, and enum/status values.
   - If no protocol field changed, say so explicitly.

4. Which golden tests were run, and is verification adequate
   - List exact commands or state that no tests were run.
   - Distinguish golden/regression tests from incidental tests.
   - If no golden tests exist, recommend the smallest scenario that should become one.
   - **Verification adequacy**: When changes involve caching, database schema, messaging protocols, transaction consistency, or cross-service calls, flag whether verification is sufficient even if the diff is small. Evaluate: are hot/cold data paths, cache invalidation, and backward-compatible reads covered? Does the test environment reflect production data distribution? Are there verification blind spots that are hard to automate?

5. Where is the AI uncertain
   - Identify assumptions, unverified compatibility, missing tests, ambiguous ownership, migration uncertainty, or areas where behavior depends on prompts/model output.
   - **Focus on three hallucination risk types**:
     - Business-semantic errors: The AI fills in based on generic understanding, but the project's actual definitions differ (e.g., state-machine meanings, permission models, billing semantics diverge from industry defaults).
     - Boundary-condition errors: The AI covers the happy path but misses extreme inputs, concurrency, timeouts, retries, or partial-failure scenarios.
     - Dependency-cognition errors: The AI assumes a dependency behaves per documentation or common patterns, but the actual project differs due to legacy reasons or special configuration.

6. Change diffusion path
   - Assess which architecture layers (controller / service / repository / message / config, etc.) and module boundaries the change touches simultaneously.
   - The more cross-layer, cross-module, and state-consistency-involved the change is, the higher the inspection level should be.
   - Watch specifically for the AI "following the chain all the way down," causing a single commit's scope to exceed expectations.

7. Whether known architecture constraints were breached
   - Check the change against explicit constraints in the project's CLAUDE.md, architecture docs, and coding conventions.
   - Common breach patterns: service layer depending directly on controller DTOs, new synchronous remote calls on critical paths, hard deletes instead of soft deletes, cross-layer direct repository access, domain exceptions leaking infrastructure details.
   - If the project lacks explicit constraint documentation, note "Project lacks explicit architecture constraints; consider adding them."

Use this structure:

```markdown
**Risk Review**

- Behavior changes: ...
- Affected existing features: ...
- Protocol/field changes: ...
- Golden tests & verification adequacy: ...
- AI uncertainties (including hallucination risks): ...
- Change diffusion path: ...
- Architecture constraint breaches: ...

**Recommendations**
- ...
```

## Risk Classification

Classify the change using one or more categories. Each category carries a review level that signals how rigorously the commit should be inspected:

| Category | Trigger conditions | Review level |
| --- | --- | --- |
| Tuning | Prompt, threshold, ranking, scoring, or strategy tweaks; goal is no change to protocol or main-flow contracts | 🟢 Low: quick confirmation suffices |
| Behavior change | User-visible output, routing results, error handling, resume/rerun behavior, or default strategy changed | 🟡 Medium: confirm impact scope and regression coverage |
| Protocol change | JSON, message, session, memory, config, API parameter, enum/status, or frontend payload field changes | 🟠 Medium-high: confirm compatibility strategy and migration plan |
| Architecture change | Responsibility boundaries, call chains, lifecycle, or state ownership of Planner/Skill/Action/Runtime/Memory/Tool changed | 🔴 High: senior engineer or TL must confirm each item |

If a change fits multiple categories, keep all relevant categories and adopt the **highest** review level among them. Do not down-classify a protocol or architecture change as tuning just because the diff is small.

### Review-level requirements

- 🟢 Low: clear commit-message classification suffices
- 🟡 Medium: impact scope must list concrete modules/chains; golden tests must be run or explicitly marked as missing
- 🟠 Medium-high: additionally, compatibility strategy (backward-compatible / breaking) and migration steps must be stated
- 🔴 High: additionally, a human must confirm design intent; attaching a design note or ADR link is recommended

## Commit Gate

Do not create a commit during the first review pass.

Only help commit when both are true:

- The user has confirmed the review is acceptable or has accepted the residual risks.
- The user explicitly asks Codex to commit.

Before committing, verify the staged set:

- If nothing is staged, ask whether to stage the reviewed files or stage them if the user already requested that exact scope.
- If unrelated files are staged, stop and ask for confirmation before including them.

## Commit Message Requirements

The commit message must include both classification and concrete change details. The notes/body should be useful to PR reviewers without reading the full diff.

Recommended format:

```text
<type>: <short summary>

Change classification: [Review level: 🟢Low / 🟡Medium / 🟠Medium-high / 🔴High]
- Tuning: <what prompt/threshold/strategy changed; omit if none>
- Behavior change: <what user-visible or agent behavior changed; omit if none>
- Protocol change: <what fields/payloads/states/compatibility strategy changed; omit if none>
- Architecture change: <what responsibility boundaries/call chains/lifecycle/state ownership changed; omit if none>

Impact scope:
- <list affected historical features, modules, chains, or golden scenarios>

Change diffusion:
- <state which architecture layers/modules this change spans; single-layer local or multi-layer cascade>

Architecture constraints:
- <state whether known architecture constraints were breached; if not, write "No constraint breach">

Verification:
- <list test commands run, or state not run and why>
- <when changes involve cache/DB/messaging/transactions, include verification adequacy assessment>

AI uncertainties:
- <list remaining assumptions, uncovered risks, hallucination risk types (business-semantic / boundary-condition / dependency-cognition); if none, write "No significant residual uncertainty">
```

Examples:

```text
feat: route action skills through session orchestrator

Change classification: [Review level: 🔴High]
- Behavior change: Planner skill hitting DATA_QUERY now executes through a unified ticket, avoiding bypass of the child session main chain.
- Protocol change: child message adds control/action_payload layered read logic, with backward-compatible read of legacy fields.
- Architecture change: parent-child session control converges from scattered Planner/DataQueryAction writes to ActionSessionOrchestrator.

Impact scope:
- Affects Planner skill, DATA_QUERY resume/rerun, artifact rollback, parent action_link state writeback.

Change diffusion:
- Spans service/orchestrator/message/repository four layers, involving parent-child session bidirectional state sync.

Architecture constraints:
- No constraint breach (ActionSessionOrchestrator follows adapter-layer isolation rule).

Verification:
- uv run pytest tests/planner_agent/test_data_query_resume.py -q
- uv run pytest tests/planner_agent/test_planner_skills.py -q
- Note: missing end-to-end golden scenario for BUILD/GOVERNANCE round-level recovery; verification coverage is incomplete.

AI uncertainties:
- Business-semantic risk: BUILD round recovery state-machine meaning may differ from generic understanding.
- BUILD/GOVERNANCE round-level recovery still lacks an end-to-end golden scenario.
```

```text
tune: adjust planner skill routing threshold

Change classification: [Review level: 🟡Medium]
- Tuning: raised skill route confidence threshold to reduce low-confidence prompt-only skill false hits.
- Behavior change: borderline inputs are now more likely to fall back to regular Planner routing.

Impact scope:
- May affect skill hit rate, regular planning fallback path, historical prompt-only skill scenarios.

Change diffusion:
- Only touches planner skill routing single layer; no cross-module spread.

Architecture constraints:
- No constraint breach.

Verification:
- uv run pytest tests/planner_agent/test_planner_skills.py -q

AI uncertainties:
- Dependency-cognition risk: threshold change has not been replayed against a real production query set; production data distribution may differ from test set.
```

Keep the first line concise. Put detailed classification in the body, not only in the subject.

## Final Response After Commit

After a successful commit, summarize:

- commit hash
- classification categories
- tests run
- any residual risk

If the commit did not happen, state exactly why.
