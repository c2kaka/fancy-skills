---
name: propagate-api-contract-changes
description: Trace and implement backend API, OpenAPI, JSON Schema, request/response, field, enum, endpoint, and protocol-version changes across every affected frontend layer. Use when a user says the backend API or schema changed, asks to sync frontend code with a new contract, rename contract fields or enum values, adapt a response mapper, change an endpoint or HTTP method, migrate a schema version, or audit the frontend impact of a backend contract change.
---

# Propagate API Contract Changes

Carry a backend contract change through the frontend without leaving stale types, mappers, form state, UI behavior, fixtures, or tests behind. Treat the contract boundary as a data flow, not a collection of matching strings.

## 1. Resolve scope and authority

Determine whether the user wants analysis only or implementation. Do not edit code for an analysis-only request.

Identify the strongest available contract sources:

1. Machine-readable schema or generated contract, such as OpenAPI or JSON Schema
2. Versioned backend interface definitions and focused backend tests
3. Explicit backend documentation or migration notes
4. Captured real request and response evidence
5. Sample payloads

Do not treat one sample payload as a complete schema. Record conflicts between sources and ask for a decision only when the ambiguity would materially change behavior or compatibility.

Before implementation, state the interpreted delta, affected boundary, compatibility assumption, and verification plan.

## 2. Model the semantic contract delta

Compare old and new behavior and classify each change as breaking, additive, or ambiguous. Cover the relevant dimensions:

- Transport: endpoint, HTTP method, headers, authentication, path, query, body, and content type
- Request: field names, nesting, requiredness, nullability, defaults, enums, formats, units, and serialization
- Response: envelope, success data, errors, pagination, status values, nullability, and deserialization
- Behavior: lifecycle, validation, idempotency, ordering, concurrency, retry, and version semantics

Express the delta in domain terms. A field rename is not merely text replacement when its meaning, source, default, or lifecycle also changed.

## 3. Trace impact through the data flow

Follow symbols, imports, call sites, and runtime data flow. Use text search for discovery, but do not use regex replacement or a finite keyword list as a substitute for understanding the contract.

Inspect every applicable layer:

1. Generated clients or schemas and their generation source
2. API client, request builder, transport wrapper, and query keys
3. Request and response types, schemas, enums, and validators
4. Boundary mappers, adapters, normalizers, and compatibility shims
5. State, cache, selectors, hooks, forms, defaults, and edit-mode hydration
6. UI labels, options, visibility, validation, empty states, and error handling
7. Downstream consumers, serializers, persisted drafts, and stored configuration
8. Mocks, fixtures, stories, tests, contract examples, i18n, and documentation

Prefer normalizing backend shapes at the boundary so transport details do not leak through the UI. Do not hand-edit generated files when the repository provides a generator.

Produce an impact matrix before coding:

| Contract delta | Affected symbols and paths | Behavior risk | Migration action | Verification |
| --- | --- | --- | --- | --- |

Include confirmed unaffected consumers when that evidence helps bound the change.

## 4. Choose a compatibility strategy

Use one explicit strategy:

- Atomic migration when backend and frontend deploy together
- Temporary dual-read or dual-write compatibility when versions overlap
- Versioned adapter when multiple contracts must remain supported
- Hard failure with a clear error when silent fallback would corrupt behavior

Do not add compatibility code without a real rollout need. For temporary compatibility, document the removal condition. Never silently swallow parsing, mapping, or validation errors.

## 5. Implement from the boundary inward

Make the smallest coherent change that completes the data flow:

1. Update or regenerate authoritative contract definitions.
2. Update transport and request construction.
3. Update boundary parsing, mapping, and normalization.
4. Update state, forms, caches, and UI behavior.
5. Update fixtures, tests, examples, i18n, and contract documentation.

Preserve product-facing labels when only wire values change. Avoid unrelated refactors unless they are required to keep one contract boundary authoritative.

## 6. Verify behavior at multiple layers

Select the smallest checks that establish the full contract path:

- Static checks: type checking, generated-code consistency, lint, and build
- Boundary checks: request serialization, response parsing, mapping, null and error cases
- Consumer checks: focused hooks, state, form hydration, validation, and UI tests
- Runtime checks: inspect the actual request and response or run a safe API smoke test when available
- Regression checks: verify old names and values have no unintended live consumers except deliberate compatibility paths

Do not describe mocks as real backend integration evidence.

When the change affects visible UI behavior and `chrome:control-chrome` is available, invoke it and verify the real rendered page in Chrome. Establish the target URL, viewport, relevant state, and reference artifact; reproduce before editing and validate the changed interaction afterward. Report any state that could not be verified.

## 7. Report with traceable evidence

Return these sections:

### Contract authority and scope

Name the sources used, interpreted version boundary, and compatibility assumption.

### Contract delta

List the semantic old-to-new changes and mark breaking or ambiguous items.

### Impact matrix

Show each affected symbol or path, its action, and verification evidence.

### Changes and verification

Summarize implementation and exact checks or runtime interactions performed.

### Remaining risks

List unresolved backend decisions, rollout dependencies, unverified states, and compatibility cleanup.

## Completion gates

Finish only when all applicable gates pass:

- Every changed request field is traced from UI or caller input to wire serialization.
- Every changed response field is traced from wire parsing to its final consumer.
- New required, optional, null, enum, default, and error semantics are represented explicitly.
- Stale names or enum values have no unintended live consumers.
- Generated artifacts come from their source generator when applicable.
- Focused verification covers success and relevant failure paths.
- Runtime or Chrome evidence is distinguished from mock-only evidence.
- Documentation and examples do not advertise the retired contract.

## Avoid these failure modes

- Updating TypeScript types without changing runtime mapping
- Blind search-and-replace for field or enum changes
- Assuming a sample payload defines requiredness or nullability
- Leaking backend response envelopes into UI components
- Adding hard-coded UI defaults to compensate for an unclear contract
- Editing generated clients directly
- Keeping old and new fields indefinitely without a removal condition
- Declaring success after compile passes while request or response behavior remains unverified
