# Visual evidence and waivers

## Three visual layers

1. Semantic: elements, copy, order, visibility, selection, disabled state, error state, focus, and keyboard behavior.
2. Geometric: bounding boxes, alignment, overlap, clipping, scroll, sticky behavior, responsive breakpoints, and safe areas.
3. Pixel: screenshot comparison with fixed viewport, theme, locale, data, fonts, and animation state.

Treat semantic or critical geometric mismatches as P0/P1. Use pixel diff as a high-recall signal, not a universal percentage oracle.

## Baseline governance

- Build the first candidate from an approved prototype or approved product state, not from the current implementation alone.
- Mark a current page without product approval `OBSERVED_CURRENT_STATE`, never approved truth.
- Let AI produce candidate old/new/diff artifacts; require explicit user approval to establish or update a baseline.
- Bind every update to a contract change. Never update snapshots merely to pass a failing test.
- Fix or deterministically mask dynamic data. Do not enlarge masks to hide relevant differences.
- Keep desktop, narrow, dialog/drawer, loading, empty, error, and completion states separate when applicable.
- Never copy approval or a baseline between repositories merely because their paths match.

## Real-environment safety

Default to a local full stack or dedicated test environment with deterministic seed and cleanup. Use production-backed/shared environments read-only. If a required journey needs writes and no safe environment exists, return `BLOCKED` and ask the user to provide or approve an environment; do not lower evidence requirements.

Record frontend and backend versions, actor/role/scope, route, test-data IDs, correlation IDs, network/console evidence, and cleanup result.

## Baseline waiver

AI may propose but never approve a waiver. Require:

- exact command, finding fingerprint, and file;
- baseline commit and current commit;
- evidence that the finding is unrelated to the change;
- owner, approver, reason, issue/run scope, and expiration;
- automatic invalidation when count, text, file, dependency, issue set, or relevant source changes.

Allow waivers only for eligible baseline gates. Never waive source conflicts, data loss, permission/scope violations, core state-machine failures, P0/P1 product regressions, or missing required evidence.
