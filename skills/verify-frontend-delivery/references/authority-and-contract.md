# Authority and contract protocol

## Authority by observable dimension

Use one authority per dimension instead of one global document priority:

| Dimension | Primary authority |
|---|---|
| Business capability, roles, permissions, state-machine meaning, success/failure semantics | Approved PRD or human product decision |
| Information hierarchy, copy, control state, operation path, visual interaction | Approved executable prototype or interaction design |
| Component API, design tokens, route mechanics, engineering boundaries | Current repository code and design-system rules |
| DTO, nullability, error envelope, versioning, concurrency, idempotency, persistence | Versioned backend contract and runtime evidence |
| Narrow task-specific observable change | Explicitly approved task contract |

Code and tests prove current behavior, not desired product intent. A screenshot proves one observed state, not a complete state machine. A mock proves frontend conformance to the mock, not backend integration.

## Source manifest

Give every behavior-bearing source a stable ID and record:

- kind and authority scope;
- real path or external identifier;
- repository-relative path when applicable;
- SHA-256 and Git blob/commit when available;
- version, provider, updated time, and parsing limits;
- adopted sections, prototype states, or screenshot regions.

Treat a missing documented path as `SOURCE_MISSING`. Treat a changed fingerprint after freeze as `SOURCE_CHANGED`. Both block verification until the contract is refreshed and approved.

## Minimum task contract

Record:

- repository, branch, base/head, route, and target files;
- requested and confirmed issue sets;
- in-scope and out-of-scope behavior;
- user-visible change and non-goals;
- authority mapping and provenance;
- conflicts, assumptions, open questions, and owners;
- acceptance scenarios and required evidence;
- risk level and required gates;
- approval identity and time.

Add risk-triggered sections:

- forms: defaults, create/edit, reset, validation, final submission;
- requests: loading, empty, error, partial, retry, stale, cancellation;
- routes: entry, same-location, Back, Forward, reload, return context;
- data mapping: raw, draft, applied, persisted, reloaded, downstream;
- permissions: actor, role, scope, forbidden behavior, 403/404 treatment;
- API: request/response, nullability, enums, version, concurrency, idempotency, errors;
- visuals: viewport, locale, theme, fixture, prototype state, responsive anchors.

## Lifecycle matrix

Require stateful work to cover at least:

```text
initial -> edit draft -> validate -> apply/complete -> save -> reload
        -> reopen/edit -> discard/undo -> downstream consumption
```

Add applicable transitions such as connect/reconnect/remove, Back/Forward, publish/unpublish, stale/read-only, retry/cancel, and destructive confirmation.

## Conflict and approval rules

Do not silently reconcile authorities. Record each conflict with affected assertions, downstream gates, decision owner, options, and recommendation. Freeze only when every high-impact conflict is resolved or explicitly blocks an independent branch.

The requested issue set and confirmed issue set must match at freeze time. A later scope change requires a contract diff and renewed approval.

## Slice rules

Use one independently provable product behavior or invariant per slice. Default to splitting UI, domain, API-contract, and migration changes unless atomicity is proven. Require red-before/green-after evidence and close the prior slice before starting the next.
