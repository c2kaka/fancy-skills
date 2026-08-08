# Code Review Checklist

Use this checklist after implementation and before requesting commit approval. Mark unsupported claims as unverified rather than passing them by assumption.

## Correctness and evidence

- [ ] The stable reproduction matches the JIRA report.
- [ ] The regression test fails for the reproduced reason before the production fix.
- [ ] The implementation addresses the proven root cause, not a downstream symptom.
- [ ] The regression test passes after the fix.
- [ ] Normal, boundary, and relevant error paths behave correctly.
- [ ] Exceptions and failed validations remain visible and actionable.

## Scope and compatibility

- [ ] The diff contains only the approved fix, tests, and required documentation or migration artifacts.
- [ ] API, data, configuration, and persisted-state compatibility were evaluated.
- [ ] Schema changes use the repository's migration mechanism and consider upgrade and rollback behavior.
- [ ] Callers and downstream consumers remain compatible or are updated coherently.
- [ ] No unrelated cleanup or refactor is mixed into the fix.

## Security and reliability

- [ ] External input is validated at the correct boundary.
- [ ] No SQL, command, path, template, or browser injection risk was introduced.
- [ ] Authentication, authorization, and tenant boundaries remain intact.
- [ ] Secrets, tokens, personal data, and `.env` contents are absent from code, logs, tests, and the staged diff.
- [ ] Concurrency, idempotency, retries, timeouts, and partial-failure behavior were considered where relevant.

## Performance and maintainability

- [ ] The fix does not introduce avoidable repeated I/O, N+1 queries, unbounded work, or resource leaks.
- [ ] The implementation follows repository architecture, naming, and style conventions.
- [ ] Comments explain non-obvious reasons rather than restating code.
- [ ] Temporary compatibility code has a documented removal condition.
- [ ] Relevant documentation and examples reflect the corrected behavior.

## Commit boundary

- [ ] The user approved the final diff and proposed commit.
- [ ] Only explicit approved paths are staged.
- [ ] `.env`, unrelated worktree changes, generated artifacts, and temporary attachments are not staged.
- [ ] The workflow stops after the local commit, with no push or merge request.
