---
name: spec-to-executable-tickets
description: Convert product materials such as PRDs, HTML prototypes, documents, API contracts, existing tickets, code, and runtime behavior into a human-owned Delivery Spec, Interaction Spec, evidence-backed gap analysis, and dependency-ready executable tickets; optionally hand approved tickets to the configured Ticket Queue Executor for implementation and real Chrome acceptance. Use only when the user explicitly invokes `$spec-to-executable-tickets`; never select this skill implicitly.
---

# Spec to Executable Tickets

Turn probabilistic product materials into an auditable implementation contract. Keep product semantics human-owned, use AI for exhaustive analysis and evidence collection, and prevent unconfirmed inference from entering implementation as fact.

## Select the operating mode

Choose a mode from the user's explicit request:

- **Analysis Mode**: ingest materials, converge the specification, investigate the repository, analyze gaps, and create `ready-for-agent` Tickets. Do not modify product code.
- **Delivery Mode**: complete Analysis Mode, pass the Delivery Gate, hand ready Tickets to the configured `ticket_queue_executor` Agent, and verify the resulting implementation. Enter this mode only when the user explicitly asks to implement or names Delivery Mode.

Default to Analysis Mode when the invocation does not clearly authorize implementation. A report-only request also forbids writing artifacts; otherwise write the specification and Ticket artifacts using repository conventions without committing or pushing.

## Preserve authority boundaries

Treat formally delivered PRDs and prototypes as the baseline of stated product intent, not as automatically complete truth.

- Treat explicitly written or demonstrable behavior as baseline-confirmed intent.
- Mark AI-created connections or completions as derived or assumed; never promote them through repetition.
- Treat missing behavior as undefined, not unnecessary.
- Route contradictions and decisions that change user outcomes to the Product Decision Owner.
- Require joint product and engineering confirmation when feasibility, cost, consistency, migration, security, or contracts would change product behavior.
- Let engineering choose implementation details only when the observable product semantics remain unchanged.

Require human decisions for goals, scope, success criteria, roles, permissions, domain meaning, state invariants, failure and compensation policy, irreversible actions, data and external contracts, product tradeoffs, and Product Outcome acceptance.

## Discover the repository protocol

Before creating artifacts:

1. Read every applicable `AGENTS.md`, product and architecture documentation, Ticket templates, lifecycle definitions, review conventions, and existing specification directories.
2. Inspect the worktree and preserve unrelated or uncommitted changes.
3. Discover the repository's existing Ticket status, dependency, evidence, and completion fields. Map this skill's concepts onto them; do not create a competing queue.
4. Identify the selected capability boundary, Product Decision Owner, requested mode, source materials, and expected final state.
5. Use the default artifact layout only when the repository has no established equivalent. Read [artifact-model.md](references/artifact-model.md) before creating or updating the specification model.

## Ingest and classify sources

Create or update a Source Manifest with stable source IDs, paths or links, content fingerprints, versions, providers, authority scopes, and parsing limitations.

Use the appropriate available Skill for specialized inputs rather than reimplementing parsing. For HTML prototypes or live UI, inspect the behavior in a real browser; prefer `chrome:control-chrome` and the user's Chrome state. For API or Schema materials, trace contract semantics rather than treating field text as standalone product intent.

Classify every behavior-bearing assertion as one of:

- confirmed explicit intent;
- human-confirmed decision;
- derived conclusion;
- assumption;
- open question;
- contradiction;
- superseded statement.

Record provenance. Product materials describe desired behavior, code and runtime evidence describe current behavior, hard constraints describe prohibited behavior, and AI inference describes only a possibility.

## Build the executable specification

Normalize the selected capability into four linked views:

1. **Product intent**: actors, problem, goals, success measures, scope, and non-goals.
2. **Behavior specification**: domain objects, rules, invariants, states, transitions, happy paths, exceptions, cancellation, recovery, and side effects.
3. **Interaction and contract specification**: screens, user actions, UI states, data meanings, APIs, events, permissions, and cross-layer boundaries.
4. **Decision and uncertainty model**: decisions, assumptions, conflicts, open questions, owners, blockers, and downstream impact.

Assign stable IDs only to behavior-bearing objects: `REQ-*`, `RULE-*`, `STATE-*`, `SCN-*`, `DEC-*`, `UNK-*`, and `GAP-*`. Preserve IDs across reruns and wording changes.

For frontend work, read [frontend-interaction-contract.md](references/frontend-interaction-contract.md). Observe executable prototypes in the browser, extract interaction points and state transitions, and distinguish demonstrated behavior from missing states and demo-only implementation shortcuts.

## Run human decision gates

Enforce four gates:

1. **Intent Gate**: confirm users, problem, scope, non-goals, and success measures.
2. **Semantic and Risk Gate**: resolve high-impact ambiguity in business behavior, permissions, data, contracts, failure policy, or irreversible operations.
3. **Delivery Gate**: confirm that specifications, gaps, Ticket slices, dependencies, and acceptance scenarios preserve the intended product semantics.
4. **Product Outcome Gate**: leave final product acceptance to the Product Decision Owner after implementation verification.

Generate Decision Packets instead of asking vague clarification questions. Rank decisions by downstream unlock count, risk, reversibility, shared-contract impact, and urgency. Present the smallest batch that unlocks the most work, usually no more than five to seven decisions.

Never silently default a high-impact decision. Use an automatic default only for a low-risk reversible detail covered by an existing, human-approved project policy. Read [review-and-ticket-contracts.md](references/review-and-ticket-contracts.md) before generating Decision Packets or the product review bundle.

## Prove readiness before gap analysis

Check that the selected branch defines:

- actors, permissions, goals, and non-goals;
- domain objects, states, transitions, rules, and invariants;
- primary, exceptional, recovery, and cancellation scenarios;
- data, API, event, and cross-system effects;
- applicable security, consistency, compatibility, and performance constraints;
- executable acceptance examples;
- provenance and owners for material decisions;
- explicit branch blockers for every unresolved high-impact unknown.

Do not require a global freeze. Block only the specification and Ticket branches that depend on an unresolved decision. A shared domain model, public contract, or core state-machine decision may naturally block many branches.

## Perform evidence-backed gap analysis

Compare desired behavior against the current observable system, not PRD paragraphs against filenames.

For each `SCN-*`, `RULE-*`, or `STATE-*`:

1. Inspect relevant code, tests, contracts, migrations, configuration, and existing Tickets.
2. Run focused diagnostics or the local stack when static evidence cannot establish behavior.
3. Record what the specification requires, what current evidence proves, the first divergence, affected layers, risk, confidence, and verification method.
4. Classify the result as product decision, material conflict, domain fact, interaction design, technical discovery, existing-implementation discovery, confirmed implementation gap, or acceptable documented assumption.
5. Create an implementation Ticket only for a confirmed difference where the desired behavior is already settled.

Do not label absence of evidence as a confirmed gap. Do not describe mocks, fixtures, bypassed authentication, or synthetic responses as real integration evidence.

## Generate executable Tickets

Adapt to the repository's Ticket protocol. Use the repository-equivalent of `ready-for-agent` only after the Ticket contract and Evidence Gate pass.

Prefer vertical, user-observable slices. Define a frontend capability as actor + precondition + action + state transition + result + side effect + failure and recovery behavior. Do not split merely into frontend, backend, or database work unless a shared contract, migration, or platform change has an independently verifiable result.

Require every Ticket to contain a bounded outcome, traceability IDs, current evidence, exact gap, scope and non-goals, affected boundaries, dependencies, inputs and outputs, invariants, implementation constraints, executable acceptance scenarios, compatibility requirements, risks, and completion evidence. Use the admission checklist in [review-and-ticket-contracts.md](references/review-and-ticket-contracts.md).

## Handle changes incrementally

On rerun:

1. Compare source fingerprints and semantic meaning against the current model.
2. Preserve human decisions, stable IDs, and unaffected branches.
3. Generate a Change Proposal instead of overwriting confirmed semantics.
4. Mark downstream scenarios, gaps, and Tickets `needs-impact-review` when behavior, data, contracts, dependencies, or acceptance changes.
5. Update low-impact wording mechanically only when observable behavior is unchanged.
6. Retain replaced objects as `superseded` with a replacement link and reason.
7. Refuse an uncertain automatic match and present candidate mappings for review.

Never recreate the entire model merely because source wording changed. Recompute only affected dependency branches and avoid duplicate decisions or Tickets.

## Complete Analysis Mode

Stop Analysis Mode when:

- the selected scope and non-goals are explicit;
- unresolved high-impact items are resolved or represented as owned branch blockers;
- the Delivery and Interaction Specs pass readiness checks;
- every confirmed gap has code or runtime evidence;
- every executable Ticket has closed dependencies, traceability, scope, acceptance, and validation instructions;
- ready and blocked branches are reported separately;
- the product review bundle, executable queue, and remaining-blocker report are current.

Do not modify product code in this mode. Report created or updated artifacts, confirmed gaps, decision requests, ready Tickets, blocked branches, evidence limits, and recommended next Gate.

## Complete Delivery Mode

After the Delivery Gate, use the configured `ticket_queue_executor` Agent when available. If it is unavailable, stop with a handoff instead of silently merging product analysis and implementation authority.

Require the executor to process one eligible Ticket at a time, respect dependencies, preserve user work, validate each acceptance criterion, record exact evidence, and rescan after every completion or external block.

For UI Tickets:

1. Implement observable behavior rather than copying prototype DOM, generated CSS, or demo data.
2. Reuse the repository's architecture and design system when it preserves the specified result.
3. Prefer `chrome:control-chrome` to compare prototype and application at relevant viewports and states.
4. Verify visual anchors, interaction scenarios, keyboard and focus behavior, console, network requests, real API results, persistence, and refresh behavior.
5. Distinguish visual similarity, interaction correctness, and real integration; require all applicable layers.

Stop Delivery Mode when no Ticket remains in progress, every executable branch is implementation-verified, remaining blockers have evidence and owners, UI work has real Chrome evidence, and the Product Outcome review list is ready. Never mark `product-accepted` without an explicit human decision or a pre-approved low-risk acceptance policy.

## Produce an auditable handoff

Report:

- mode and selected capability;
- ingested and changed sources;
- confirmed decisions and unresolved Decision Packets;
- Delivery and Interaction Spec readiness;
- confirmed gaps with evidence confidence;
- ready, blocked, completed, and superseded Tickets;
- traceability and impact-review changes;
- implementation and browser verification evidence when applicable;
- Product Outcome scenarios awaiting human acceptance;
- files changed and any limitations.

Do not commit, push, create a merge request, deploy, or broaden external side effects unless the user explicitly authorizes it.
