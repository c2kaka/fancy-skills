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

## Change locality

- [ ] The variation that distinguishes the good case from the bad case is named with concrete values in the packet.
- [ ] The owner boundary and the receiver table (handles / missed / indifferent) are backed by an actual codebase search, not intuition.
- [ ] The actual diff stays within the locality budget stated in the approved packet (theoretical scope versus touched files).
- [ ] The diff does not add the same guess, conversion, or check to several receivers for the same reason.
- [ ] If a local patch was chosen over a boundary fix, the remaining leak is recorded as a structural signal in the risks section.
- [ ] Locality did not become an excuse for a refactor: only the owner and the receivers named in the approved plan changed.

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

## Packet readability

- [ ] The Phase 5 packet opens with the plain-language outcome, not a stack trace or file path.
- [ ] The same concrete example is used for reproduction, root cause, and before/after behavior.
- [ ] Every code identifier in the decision sections is glossed on first use and is there because it pins down the cause.

## Commit boundary

- [ ] The user approved the final diff and proposed commit.
- [ ] Only explicit approved paths are staged.
- [ ] `.env`, unrelated worktree changes, generated artifacts, and temporary attachments are not staged.
- [ ] The workflow stops after the local commit, with no push or merge request.
