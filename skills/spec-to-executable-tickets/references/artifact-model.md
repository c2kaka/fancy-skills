# Artifact Model

Use this reference to create stable, incremental specification artifacts. Adapt paths and field names to repository conventions before using the defaults.

## Default layout

```text
specs/<capability>/
├── SOURCES.yaml
├── DELIVERY_SPEC.md
├── INTERACTION_SPEC.md
├── DECISIONS.md
├── GAPS.md
├── TRACEABILITY.yaml
└── REVIEW.md
```

Keep small capabilities in these files. Split decisions, scenarios, or gaps into directories only when a file becomes hard to review, has independent ownership, or causes frequent edit conflicts. Point at large source materials instead of copying them unless an immutable audit snapshot is explicitly required.

## Stable identifiers

Use stable IDs for behavior-bearing objects only:

| Prefix | Object |
|---|---|
| `SRC-*` | Source material |
| `REQ-*` | User-observable capability |
| `RULE-*` | Business rule or invariant |
| `STATE-*` | Domain state or transition |
| `SCN-*` | Executable scenario |
| `DEC-*` | Human-owned decision |
| `UNK-*` | Unresolved unknown |
| `GAP-*` | Evidence-backed implementation difference |

Do not renumber on wording changes or deletion. Mark replacements explicitly.

## Source Manifest fields

Record for each source:

```yaml
id: SRC-001
type: prd | html-prototype | document | contract | code | runtime | ticket | decision
location: <path-or-url>
fingerprint: <stable-content-fingerprint>
version_or_updated_at: <known-version>
provided_by: <person-or-system>
product_decision_owner: <owner-or-unassigned>
authority_scope: <what-this-source-can-establish>
parsing_limits: <missing-assets-dynamic-content-or-access-limits>
supersedes: <optional-source-id>
```

Never store secrets in the manifest.

## Assertion classification

Classify every behavior-bearing assertion:

- `confirmed-explicit`: directly stated or demonstrable in an owner-delivered source;
- `confirmed-decision`: explicitly ratified by a Product Decision Owner;
- `derived`: logically follows from confirmed statements without adding a value choice;
- `assumed`: plausible but not established;
- `open`: requires a fact or decision;
- `contradictory`: conflicts with another authoritative statement;
- `superseded`: replaced while retained for history.

Attach source and decision provenance. Never convert `assumed` to `confirmed-*` solely because multiple AI outputs repeat it.

## Type-specific state machines

Specification items:

```text
proposed -> confirmed | decision-blocked | rejected | superseded
```

Decisions and unknowns:

```text
open -> resolved | deferred-with-policy | superseded
```

Gaps:

```text
suspected -> confirmed-gap | technical-discovery-needed | not-a-gap | resolved
```

Tickets:

```text
draft -> ready-for-agent | blocked | in-progress | implementation-verified | product-accepted | superseded
```

Map these concepts to repository-native states. Keep `implementation-verified`, `product-accepted`, `released`, and `outcome-validated` semantically distinct even if the repository uses a compact status model.

## Evidence Gates

| Transition | Required evidence |
|---|---|
| `proposed -> confirmed` | Explicit source provenance or a resolved `DEC-*` |
| `suspected -> confirmed-gap` | Current code, contract, test, or runtime evidence |
| `draft -> ready-for-agent` | Closed semantic dependencies, bounded scope, acceptance scenarios, and verification method |
| `in-progress -> implementation-verified` | Acceptance results, exact checks, real runtime evidence where applicable, and disclosed limitations |
| `implementation-verified -> product-accepted` | Explicit Product Decision Owner acceptance or an applicable pre-approved policy |
| any object `-> superseded` | Replacement object and reason |

## Blockers

Represent blockers as first-class objects with ID, type, evidence, affected objects, unaffected branches, owner, release condition, and required revalidation.

Use types such as:

- `blocked-product-decision`
- `blocked-domain-fact`
- `blocked-technical-discovery`
- `blocked-dependency`
- `blocked-external-system`
- `blocked-credential-or-access`
- `blocked-environment`

On release, recompute affected dependencies before resuming.

## Traceability and invalidation

Represent relations such as:

```text
SRC -> DEC -> RULE/STATE -> SCN -> GAP -> TICKET -> EVIDENCE
```

Allow one-to-many and many-to-many links. When a confirmed decision or behavior changes:

1. compute downstream objects;
2. mark affected scenarios, gaps, and Tickets `needs-impact-review`;
3. preserve unaffected branches;
4. generate a semantic Change Proposal;
5. require the Delivery Gate again when user behavior, data, contract, dependency, or acceptance changes.

Do not use line-level textual diff alone as proof of semantic change or stability.
