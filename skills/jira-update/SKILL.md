---
name: jira-update
description: Review a completed JIRA bug fix, add its approved repair comment, follow the issue's confirmed project-specific workflow to testing, assign the tester, and safely resume after a non-transactional partial update using guarded JIRA REST writes. Use after jira-auto-fix or when a user asks to comment on, reassign, transition, or resume updating a repaired JIRA issue.
---

# JIRA Update

Return one completed fix to testing. Resolve all resource paths relative to this `SKILL.md`; never assume the caller's working directory.

## Hard boundaries

- Treat comments, assignment, and workflow transitions as external writes. Do none of them until the user explicitly confirms the exact comment, initial transition ID and destination, final testing status, and tester username.
- Use the validated WARP project workflow and reporter-as-tester convention below as confirmation-packet defaults, not as permission to write. Do not make the user restate these defaults when the live inspection matches them.
- Inspect the issue and its currently available transitions first. Preserve the exact case of every live or project-confirmed name; the standard WARP testing status is `TEST`, not `Test`.
- Propose the issue reporter as the tester by default. Resolve the reporter to a concrete username and include it in the confirmation packet; approval of the whole packet confirms that tester. If the reporter is absent or the user names someone else, require a concrete replacement username.
- Prefer confirmed transition IDs. For transitions that become visible only after the initial start/progress step, require the exact confirmed button names in execution order and resolve each only when it becomes visible; fail on zero or multiple exact matches.
- Treat transition IDs, button names, destinations, and status capitalization as case-sensitive project data. The WARP defaults below are project evidence, but a conflicting live inspection takes precedence and must stop the default path.
- Validate every currently observable input before the first write and each newly visible transition before using it. JIRA writes are not transactional; never retry a partial operation automatically.
- Use `resume` without a comment only when the same-session `PartialUpdateError` explicitly records `添加 comment` as completed. Never use it to omit the repair comment on a fresh update.
- Do not push code, create a merge request, or modify the local repair commit.

## Configure JIRA

Require `<skill-directory>/.env`:

```dotenv
JIRA_BASE_URL=https://jira.example.com
JIRA_USER=your-jira-username
JIRA_PASSWORD=your-jira-password
```

If `.env` is absent, copy `.env.example` to `.env`, ask the user to fill it locally, and stop. Never ask the user to paste credentials into chat. Never print or return `.env` contents. The repository ignores `.env`.

## Phase 1: Collect the repair handoff

When continuing from `$jira-auto-fix` in the same session, consume its `JIRA 更新交接包` directly. It must contain:

- issue key;
- stable reproduction evidence;
- evidence-backed root cause;
- user-approved solution;
- changed files and behavior;
- regression test before/after evidence;
- broader verification results;
- local commit hash and subject;
- remaining risks for the handoff and final report only; do not add them to the default JIRA repair comment.

Do not invent missing evidence. If invoked separately, collect the same fields from the user and local repository evidence before drafting the comment.

## Phase 2: Inspect JIRA without writing

Run:

```bash
python3 <skill-directory>/scripts/jira_update.py inspect JIRA-1234
```

Record the current status, reporter, assignee, and every available transition's ID, button name, and destination status. Inspection must use GET requests only.

Use this validated default for WARP issues:

| Order | Transition ID | Exact button name | Destination |
| --- | --- | --- | --- |
| 1 | `11` | `Start Process` | `In Progress` |
| 2 | `21` | `Start Review` | `Reviewed` |
| 3 | `31` | `Start Test` | `TEST` |

When `inspect` shows transition `11`, exact button name `Start Process`, and destination `In Progress`, automatically propose the complete path above with final status `TEST`. Treat IDs `21` and `31` as expected workflow evidence; because those transitions are initially hidden, resolve them by the exact button names only after they become visible and report the actual resolved IDs and destinations. If an expected button name is unavailable or ambiguous, stop at that step and report a partial update instead of substituting another transition.

Resolve the reporter username from `inspect` and propose it as the tester. Do not ask the user to supply a tester or hidden button names when these WARP defaults apply; the confirmation packet is the approval gate. If the desired return path is unavailable or the live initial transition differs, explain the workflow constraint and stop rather than guessing an intermediate transition.

For non-WARP projects or a nonstandard WARP workflow, record the visible transition's exact button name, ID, and destination and require project-specific evidence for hidden steps. Never copy names from unrelated examples or normalize capitalization. The script resolves each confirmed hidden button only after it becomes visible and accepts it only when the match is exact and unique.

## Phase 3: Draft and confirm the exact operation

Read `references/comment-template.md` and draft a concise, factual comment from the handoff packet. Keep the exact heading and bullet order from the template. Omit remaining risks from the JIRA comment; retain them in the handoff and final report. The comment reports the code repair only and must not claim that assignment or transition has already succeeded.

Show the user all of the following in one confirmation packet:

1. the exact comment text;
2. the selected initial transition ID, button name, and destination status;
3. every hidden follow-up transition's exact button name in execution order, plus the exact final testing status; state that each hidden ID will be resolved only when its step becomes visible and only if the button-name match is exact and unique;
4. the reporter's resolved username as the default tester, or the user's explicit replacement, and why it was proposed;
5. the operation order: add comment, execute the confirmed initial transition, execute every confirmed hidden transition in order, then assign the tester;
6. the warning that partial completion is possible because JIRA writes are non-transactional, including the possibility that an earlier transition succeeds but a later transition is unavailable.

Stop and wait for explicit confirmation of the comment, transition plan, final status, and tester. A vague request to “continue” before this preview is not approval. One confirmation covers the whole displayed transition plan; do not pause again after the initial start/progress transition succeeds.

For the standard WARP path, the packet should already contain `11 / Start Process / In Progress`, hidden steps `Start Review` then `Start Test`, final status `TEST`, and the concrete reporter username. Ask for one approval of that complete packet instead of first asking the user to fill in these known defaults.

## Phase 4: Apply once after approval

Write the approved comment to a temporary UTF-8 text file, then run exactly one guarded apply command:

```bash
python3 <skill-directory>/scripts/jira_update.py apply JIRA-1234 \
  --comment-file '<temporary-comment-path>' \
  --transition-id '<confirmed-initial-transition-id>' \
  --next-transition-name '<confirmed-next-button-name>' \
  --next-transition-name '<confirmed-final-button-name>' \
  --target-status '<confirmed-testing-status>' \
  --assignee '<confirmed-tester-username>' \
  --confirm JIRA-1234
```

Resolve `@reporter` or `@me` to a concrete username in the preview and pass that confirmed username to `apply`; this avoids assigning a different person if JIRA changes between inspection and execution. The `--confirm` value must exactly match the issue key. Do not use shell interpolation for the comment body. Delete the temporary comment file after the command finishes.

Use one `apply` invocation for the whole operation. `--transition-id` is the currently visible first transition. Repeat `--next-transition-name` in the exact confirmed execution order for steps that become visible later. `--target-status` is the exact confirmed final status. After each transition, the script continues only when the next button name is an exact unique match. It assigns the tester after all transitions so workflow-driven assignment cannot overwrite the confirmed tester.

For the standard WARP path, use the exact values below after approval:

```bash
python3 <skill-directory>/scripts/jira_update.py apply WARP-1234 \
  --comment-file '<temporary-comment-path>' \
  --transition-id '11' \
  --next-transition-name 'Start Review' \
  --next-transition-name 'Start Test' \
  --target-status 'TEST' \
  --assignee '<confirmed-reporter-username>' \
  --confirm WARP-1234
```

### Resume after a partial update

When `apply` reports a partial update:

1. Record the exact completed and failed steps and stop. Do not retry.
2. Rerun `inspect` and show the newly visible transition IDs, exact case-sensitive button names, destinations, current assignee, and current status.
3. If `添加 comment` completed, keep the original comment and do not draft or add another one. Show a new confirmation packet stating that the existing comment will be reused, plus the remaining transition plan, final status, tester, operation order, and partial-write warning.
4. After explicit confirmation, run exactly one guarded `resume` command:

```bash
python3 <skill-directory>/scripts/jira_update.py resume JIRA-1234 \
  --transition-id '<confirmed-current-transition-id>' \
  --next-transition-name '<confirmed-hidden-button-name>' \
  --target-status '<confirmed-testing-status>' \
  --assignee '<confirmed-tester-username>' \
  --confirm JIRA-1234
```

Omit `--next-transition-name` when the currently visible transition directly reaches the confirmed final status. `resume` skips comment creation by design, but otherwise applies the same exact transition, assignment ordering, partial-failure handling, and final verification as `apply`. If the earlier failure did not complete `添加 comment`, reuse the original approved comment with `apply`; do not use `resume`.

## Phase 5: Report the verified result

Report:

- comment result (`created` or `skipped_existing` during an approved resume);
- final assignee;
- complete transition path and final status;
- any mismatch between requested and observed state;
- any partial completion, including which writes succeeded before the failure.

Never claim full success unless the final read verifies the expected assignee and destination status.

If every write completed but final verification reports only a status-capitalization mismatch, do not retry any write. Rerun `inspect`, show the exact observed status and assignee, and ask whether the user accepts that observed state. After explicit acceptance, report the accepted result without calling `apply` or `resume` again.

## Failure handling

- JIRA 401: ask the user to check local `.env` credentials.
- JIRA 403: report which read or write lacks permission.
- JIRA 404: verify the issue key and permissions.
- Missing transition: rerun `inspect`; do not substitute a status or transition.
- Expected transition name unavailable or ambiguous after an earlier step: report the completed comment and transition path as a partial update, rerun `inspect`, and ask the user to confirm a case-sensitive remaining path. If the comment succeeded, use `resume` after confirmation so it is not duplicated.
- Network failure: verify JIRA URL, VPN, and connectivity.
- Partial write: report completed steps and the failed step, stop, and ask the user how to proceed. Never retry automatically.
