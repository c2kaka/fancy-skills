---
name: review-coding-agent-design
description: Review coding-agent design documents and their corresponding code or diffs for design quality, complexity reduction, design-to-code consistency, error semantics, and evidence-backed verification. Use when Codex needs to judge whether an agent-produced design and implementation are structurally sound, not merely whether the diff is syntactically correct or ready to commit.
---

# Review Coding Agent Design

Review the design intent and implementation as one system. The primary question is whether the work reduces lifecycle complexity while preserving the stated goals, constraints, and invariants.

This is a read-only review by default. Do not edit code, commit, push, approve a change, or write to an external system unless the user separately asks for that action.

## Route the Inputs

Accept one or more of these artifacts:

- a design document, plan, ADR, RFC, or architecture diagram
- requirements, issue descriptions, or acceptance criteria
- implementation code or a Git diff
- tests, command output, screenshots, traces, or other verification evidence

State what is and is not available before reaching a verdict.

- With only a design document, review the design but do not claim implementation alignment.
- With only code, reconstruct the apparent intent from authoritative project sources and label inferred intent explicitly.
- With both design and code, treat design-to-code traceability as required.
- Missing evidence is an uncertainty or verification gap, not proof that behavior is correct or incorrect.

## Read the Project Before Judging It

Inspect the highest-signal sources first: repository instructions, requirements, architecture decisions, schemas and public contracts, the target design, changed code, focused tests, and relevant history. Prefer project-specific facts over generic conventions.

Separate every important statement into one of four classes:

- source-backed fact
- design decision
- reviewer inference
- unresolved question

Do not invent business semantics, protocols, components, or constraints to complete the review.

## Review Workflow

### 1. Reconstruct the problem

Extract the goal, constraints, invariants, non-goals, assumptions, failure model, and rollout or compatibility boundaries. Ask what must remain true after the change, including under retries, partial failure, concurrency, migration, and rollback when relevant.

If the document mainly lists implementation steps, reconstruct the actual design problem before evaluating the proposed solution.

### 2. Evaluate the design argument

Check whether the design:

- explains why the problem exists and why the chosen boundary addresses it
- distinguishes current facts from proposed decisions and assumptions
- considers callers, maintainers, operators, security boundaries, and future change
- presents genuinely different alternatives for important, costly-to-reverse decisions
- makes trade-offs and rejected alternatives explicit
- uses experiments for uncertain, reversible decisions instead of pretending certainty

Read [references/review-model.md](references/review-model.md) for the complexity model and decision tests. Apply those principles as comparison tools, not universal style laws.

### 3. Trace design claims into code

Build a compact traceability matrix for material claims:

`design claim -> implementation evidence -> verification evidence -> status`

Use `implemented`, `partially implemented`, `contradicted`, or `unverified` as statuses. Check both directions:

- promises in the document that the code does not fulfill
- behavior, state, dependencies, or failure modes introduced by code but absent from the document

Trace at least one critical flow end to end when the change crosses components. Follow data ownership, dependency direction, state transitions, errors, and externally visible effects rather than reviewing files in isolation.

### 4. Analyze complexity mechanisms

Judge the system using evidence for:

- change amplification
- cognitive load
- unknown unknowns
- module depth and interface cost
- information leakage and duplicated knowledge
- dependency and coordination surface
- state ownership and lifecycle clarity
- error semantics, recovery ownership, and observability
- generality versus speculative abstraction
- local optimization versus whole-system simplicity

Do not create a synthetic total score. Explain the causal mechanism: what knowledge is exposed, which boundary multiplies it, who must coordinate, and how a future change or failure propagates.

### 5. Check coding-agent failure modes

Look specifically for:

- invented fields, protocols, business rules, APIs, or success claims
- scope drift across layers or modules
- hard-coded cases, finite keyword rules, or local heuristics standing in for semantic design
- swallowed errors or a fallback that disguises corruption or unavailability
- code overfit to visible tests without a coherent abstraction
- duplicate mechanisms that bypass the repository's authoritative path
- shallow wrappers, helpers, or services that add interfaces without hiding meaningful complexity
- local patches that ignore concurrency, lifecycle, compatibility, security, or cross-component consistency
- docs that claim verification without reproducible evidence
- terminology that changes meaning between requirements, design, code, and tests

Do not label a pattern defective merely because an agent produced it. Tie every finding to repository evidence and an observable risk.

### 6. Challenge important decisions

For a high-impact or hard-to-reverse decision, develop at least one genuinely different design and compare both against the same constraints. Do this only where the comparison can change the outcome; do not force multiple designs for cheap, local, reversible choices.

### 7. Produce the report

Lead with findings ordered by severity, then give the verdict and supporting analysis. Read [references/output-contract.md](references/output-contract.md) before writing a full review.

Write in the language requested by the user; otherwise match the user's language. Keep source identifiers, API names, and established project terminology unchanged.

Every actionable finding must include:

- a concise claim
- precise source or code evidence
- the complexity or correctness mechanism
- affected behavior and failure scenario
- a proportionate correction direction
- a way to verify the correction

Keep open questions separate from confirmed findings. Do not inflate severity to compensate for missing evidence.

## Review Boundaries

- Deep modules are not an argument for large modules without cohesion, ownership, or observability.
- Small methods, services, TDD, comments, and single responsibility are not inherently good or bad. Judge their system-level costs and benefits.
- Defining errors out means removing unnecessary exceptional states through better semantics. It never means ignoring network, machine, permission, security, or data-integrity failures.
- A simple interface that hides latency, consistency, resource, or recovery costs without making them observable has displaced complexity, not reduced it.
- Tests are design evidence and executable contracts, but passing tests do not by themselves prove the abstraction or architecture is sound.
- Comments should preserve intent, invariants, constraints, units, concurrency, lifecycle, and public contracts rather than restate syntax.

## Relationship to Nearby Skills

Use this skill for design quality and design-to-code consistency. Use `change-risk-review` when the main job is classifying the delivery risk of the current Git changes before commit. Use `analyze-ai-agent-codebase` when the main job is understanding an unfamiliar agent repository. Use `ai-agent-framework-design-guide` when the main job is authoring a framework design document.
