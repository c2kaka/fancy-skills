# Risk and required gates

Risk is cumulative. Higher levels include all lower-level gates. Upgrade risk when uncertain; never downgrade it to fit available time or tooling.

| Risk | Typical change | Additional required gates |
|---|---|---|
| `R0` | Documentation or no-runtime-impact test organization | `L0_SOURCE`, `L1_IMPACT`, `L2_STATIC` |
| `R1` | Copy, icon, pure presentation, local layout | `L3_UNIT`, `L5_BROWSER`, `L7_VISUAL` |
| `R2` | Form, state, route, interaction, mapper, cache | `L3_STATE`, `L6_REAL_PAGE` |
| `R3` | API, permission, persistence, publish, cross-stack contract | `L4_CONTRACT`, `L4_BUILD`, `L6_REAL_BACKEND` |
| `R4` | Major version, migration, rebase, cross-domain combination, release | `L8_UNION_REGRESSION`, `L8_INDEPENDENT_REVIEW` |

## Gate intent

- `L0_SOURCE`: prove all adopted sources exist, match frozen fingerprints, and have no unresolved authority conflict.
- `L1_IMPACT`: map diff and dependencies to observable behaviors, state authority, consumers, and regression scenarios.
- `L2_STATIC`: run diff check, changed formatting/lint/rules/locale, and baseline-delta checks with exact base.
- `L3_UNIT`: run the smallest red-capable unit or mapper/hook regression and adjacent affected suites.
- `L3_STATE`: prove lifecycle transitions and preservation/cleanup invariants, not isolated renders.
- `L4_CONTRACT`: prove request/response/schema/fixture round trips, unknown values, lossless scalars, and compatibility.
- `L4_BUILD`: build every affected workspace or package and separate new failures from baseline.
- `L5_BROWSER`: exercise real components in Chromium with semantic assertions and explicit fixture/adapter identity.
- `L6_REAL_PAGE`: walk the real application path with actor, route, state, reload/history, console, and network evidence.
- `L6_REAL_BACKEND`: prove the versioned backend and real adapter path, including failure/recovery and side effects.
- `L7_VISUAL`: compare approved reference and real page at fixed state, viewport, theme, locale, and data.
- `L8_UNION_REGRESSION`: for merge/rebase, prove the orthogonal union of both sides' behaviors, not only conflict-marker absence.
- `L8_INDEPENDENT_REVIEW`: use a fresh Auditor context and review the full affected slice after fixes.

## Impact analysis

Combine deterministic dependency evidence with model semantic analysis. Inspect changed files, imports/callers, routes, APIs/DTOs/schemas, state/persistence boundaries, locale, UI-kit, tests, and neighboring workflows. Do not use a finite keyword or path-regex table as the authority.

Every affected behavior needs a scenario or an explicit unverified item. Every changed test expectation needs an approved product assertion.

## Run profiles

- `quick`: source, diff, static delta, focused unit; target roughly five minutes.
- `standard`: complete `R1`/`R2`; target roughly twenty to thirty minutes.
- `deep`: `R3`/`R4`, real browser, cross-stack, visual, and broad regression; no hard cutoff.

Profiles schedule work; they do not remove required gates. Record `TIMEOUT` rather than silently skipping work.
