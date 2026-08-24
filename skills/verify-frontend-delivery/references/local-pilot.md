# Local pilot and forward testing

Keep the first rollout explicit, local, and read-only toward product repositories. Do not modify CI or existing skills.

## Static validation

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/verify-frontend-delivery/tests -p 'test_*.py' -v
uvx ruff check skills/verify-frontend-delivery tests
uvx ruff format --check skills/verify-frontend-delivery tests
uv run --with pyyaml python /path/to/skill-creator/scripts/quick_validate.py skills/verify-frontend-delivery
```

Use the repository's available equivalents when `uv` or `uvx` is unavailable. Do not install global dependencies.

## Historical corpus

Use raw repository states and sources, without telling the Auditor the expected result:

- a PRD/prototype/task conflict affecting a visible control;
- a draft/applied/persisted/reloaded propagation defect;
- a reload persistence defect;
- a post-rebase history-state or combined-behavior defect;
- one narrow evidence-complete UI control;
- one evidence-complete stateful control.

Keep replay artifacts isolated by run ID. Do not let one Auditor read another Auditor's conclusions.
Create historical contracts with `scripts/gate.py prepare --base <base> --head <head>`.
Omit `--head` for a live delivery so the frozen snapshot includes the current
`HEAD`, index, worktree, and untracked-file identity. Repository drift after
freeze blocks finalization.

## Historical replay integrity

- Prefer an isolated `git archive` or equivalent exact-ref source tree outside the product repository. Do not checkout, stash, or mutate the user's worktree merely to run a historical gate.
- Reuse an existing package-manager content store when safe, but keep installed dependencies and generated test artifacts inside the run directory. Estimate and record disk usage before installing a historical dependency tree; browser replay can exceed one gigabyte.
- Git-aware changed-file tools may not work in an archive. Run their exact-ref equivalent only when its semantics are provable; otherwise record the affected gate as `BLOCKED_BY_ENVIRONMENT`. Never run the current worktree command and attribute it to the historical head.
- A later current page, screenshot, login session, build, or test result is not evidence for an earlier commit, even when the target files now match. Preserve the historical evidence boundary explicitly.
- Do not delete the archive, dependency tree, screenshots, or reports automatically. Report their paths and sizes so the user can approve cleanup separately.

## Forward-test protocol

Start fresh Auditor agents with prompts shaped like real usage:

```text
Use $verify-frontend-delivery at <skill-path> in verify mode for repository <repo>,
contract <frozen-contract>, and change <base>..<head>. Preserve the repository and
write only local run artifacts outside it.
```

Pass raw sources, contract, diff coordinates, and artifacts. Do not pass suspected bugs, intended answers, or prior summaries. Compare risk, required gates, evidence classification, and final status across independent runs.

## Pilot completion

Require:

- zero false PASS on known high-risk historical defects;
- no mock/synthetic evidence promoted to real integration/E2E;
- no baseline-red suite reported globally green;
- environment blocking classified as `BLOCKED`, not PASS or product failure;
- explainable P0/P1 results on PASS controls;
- consistent independent-Auditor risk, required gates, and final status;
- deterministic scripts, schemas, reports, and skill metadata validated.

Do not auto-delete pilot artifacts. Report paths and sizes.
