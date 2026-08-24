# Evidence and deterministic status

## Evidence levels

Use exactly these ordered evidence levels:

1. `STATIC_VERIFIED`
2. `UNIT_VERIFIED`
3. `BROWSER_FIXTURE_VERIFIED`
4. `UI_PATH_VERIFIED_WITH_SYNTHETIC_DATA`
5. `REAL_BACKEND_INTEGRATION_VERIFIED`
6. `REAL_PAGE_E2E_ACCEPTED`

Supporting statuses are `NOT_RUN`, `BLOCKED_BY_ENVIRONMENT`, `FAIL`, `TIMEOUT`, and `WAIVED_BASELINE`.

Never use a lower level to claim a higher one. A Chromium component test with a Memory Router and Mock API is `BROWSER_FIXTURE_VERIFIED`, even if it renders real React components.

## Raw gate results

Record one entry per gate:

```json
{
  "id": "L5_BROWSER",
  "status": "PASS",
  "evidence_level": "BROWSER_FIXTURE_VERIFIED",
  "summary": "Focused candidate interaction passed",
  "commands": [{"command": "...", "exit_code": 0, "duration_ms": 1234}],
  "artifacts": ["..."],
  "unverified": []
}
```

The finalizer expands required gates from risk, enforces minimum evidence rank, validates independent-Auditor identity, checks traceability sets, rechecks source fingerprints, and refuses unapproved waivers.

## Final statuses

- `PASS`: every required gate passed at sufficient evidence, with no P2 warning.
- `PASS_WITH_P2_WARNINGS`: every required gate passed and only explicitly P2 warnings remain.
- `FAIL`: a required gate proves a current regression or new error.
- `BLOCKED`: required evidence is missing, insufficient, timed out, unsafe, source-drifted, identity-mismatched, waiver-unapproved, or independent review is unavailable.

Source, repository, contract, Auditor, or traceability invalidity takes precedence because the audit cannot be interpreted safely. Otherwise a concrete regression produces `FAIL` even when another gate remains unavailable; that unavailable evidence stays explicit in the blocking reasons and unverified boundary. With no proven regression, an unavailable environment produces `BLOCKED`.

## Machine report

Treat `gate-report.json` as authoritative. Generate `gate-report.md` from it. Include:

- schema and skill version;
- run/repository/base/head/contract identity;
- requested and confirmed issue sets;
- source fingerprints and drift;
- risk, scope, impact map, and required gates;
- raw gate results and baseline delta;
- waivers, warnings, unverified items, and blocking reasons;
- artifact index and timings;
- deterministic final status.

Do not maintain a separate handwritten conclusion that can diverge from JSON.

## Resume rules

Reuse a checkpoint only when repository, base/head/diff, source manifest, contract fingerprint, skill version, gate config, waivers, and environment identity remain compatible. Recompute the impact map and invalidate affected downstream gates after any relevant change. Re-establish browser actor, route, data, and login state rather than trusting an old screenshot.
