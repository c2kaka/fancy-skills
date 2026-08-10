---
name: jira-auto-fix
description: Reproduce, diagnose, fix, test, self-review, and locally commit code for a JIRA bug using a skill-local .env and read-only JIRA REST access. Use when a user asks to fixbug or 修复 an issue such as JIRA-1234 and requires stable reproduction, evidence-backed root-cause analysis, explicit solution approval before edits, regression tests, and a local commit without push or merge request creation.
---

# JIRA Auto Fix

Fix one JIRA bug through a gated Codex workflow. Resolve resource paths relative to this `SKILL.md`; never assume the caller's working directory.

## Hard boundaries

- Treat JIRA access as read-only. Never edit, transition, comment on, or reassign the issue.
- Do not edit tracked project files or add tests until the user explicitly confirms the proposed solution.
- Do not claim stable reproduction from one observation. Require the same failure on at least two consecutive runs under the same controlled conditions. For intermittent bugs, record the sample size and failure rate and obtain user agreement on the reproduction threshold.
- Do not claim a root cause unless evidence connects it to the reproduced failure and rules out plausible alternatives.
- Preserve pre-existing worktree changes. Never stash, reset, clean, or overwrite them automatically.
- Stop after creating a local commit. Never pull, fetch, rebase, push, force-push, or create a merge request.
- Require user confirmation at both gates: before code/test edits and before the local commit.
- Require the exact JIRA issue key to appear visibly in the local commit subject.

## Configure JIRA

Require `<skill-directory>/.env`:

```dotenv
JIRA_BASE_URL=https://jira.example.com
JIRA_USER=your-jira-username
JIRA_PASSWORD=your-jira-password
```

If `.env` is absent, copy `.env.example` to `.env`, ask the user to fill it locally, and stop. Never ask the user to paste credentials into chat. Never print or return `.env` contents. The repository ignores `.env`.

## Phase 1: Establish scope and collect evidence

1. Extract the issue key and identify the target code repository.
2. Read every applicable `AGENTS.md` and repository instruction before running project commands.
3. Inspect `git status --short`, current branch, build system, and existing uncommitted changes. Record unrelated changes and keep them out of the fix and commit.
4. Query JIRA:

   ```bash
   python3 <skill-directory>/scripts/jira_issue.py query JIRA-1234
   ```

5. Inspect the description, comments, environment, versions, and relevant attachments. For an image attachment, download it to a temporary directory and inspect it directly with Codex's built-in multimodal image capability; do not invoke an OCR skill:

   ```bash
   python3 <skill-directory>/scripts/jira_issue.py download '<attachment-url>' '<temporary-output-path>'
   ```

6. Do not download unrelated attachments. The downloader accepts only HTTPS URLs from the configured JIRA origin.

## Phase 2: Reproduce before changing files

Keep tracked project files unchanged during this phase.

1. Translate the report into a controlled reproduction contract:
   - environment and starting state;
   - exact inputs and actions;
   - expected behavior;
   - actual failure signal;
   - command, route, or runtime entry point used.
2. Prefer an existing focused test or a deterministic runtime command. Do not add diagnostic code or a new test before solution approval.
3. Reproduce the same failure at least twice consecutively. Capture exact commands, relevant output, stack traces, logs, and observed state without exposing secrets.
4. If the bug is intermittent, run a bounded sample, report attempts and failures, and do not label it stable without a repeatable trigger or a user-approved statistical threshold.
5. If reproduction is blocked by missing access, data, environment, or instructions, report the attempts and ask for the missing input. Do not guess a fix.

## Phase 3: Prove the root cause and propose a solution

1. Trace the failing control flow and data flow from the reproduced signal to the responsible code.
2. Inspect callers, boundaries, state transitions, configuration, relevant tests, and `git log` or `git blame` where useful.
3. Form competing hypotheses and use evidence to eliminate them. Distinguish the root cause from downstream symptoms.
4. Define the smallest coherent fix, affected files, compatibility and migration impact, risk, and focused regression plan.
5. Present this approval packet:

   ```text
   JIRA: <issue key and summary>
   Stable reproduction: <environment, exact command/actions, 2+ matching failures>
   Expected vs actual: <behavior delta>
   Root cause: <code path and causal evidence>
   Proposed solution: <minimal file-level changes>
   Alternatives considered: <why rejected>
   Test plan: <regression, boundary, and relevant broader checks>
   Risks and impact: <compatibility, data, performance, security>
   ```

6. Stop and wait. Continue only after the user explicitly confirms the solution. If the user requests changes, revise the analysis and request confirmation again.

## Phase 4: Add the regression test, then fix

After solution approval:

1. Add the narrowest regression test that expresses the reproduced failure.
2. Run the new test before changing production code and capture that it fails for the expected reason. If this ordering is technically impossible, explain why and agree on equivalent evidence before proceeding.
3. Implement the approved minimal fix. Do not include unrelated refactors.
4. Run the regression test and confirm it passes.
5. Run relevant boundary, error, and existing regression checks in proportion to risk. Use the repository's actual build and test commands rather than assuming Maven.
6. Review the complete diff against `references/code-review-checklist.md`.

## Phase 5: Report and request commit approval

Present:

- reproduction evidence and confirmed root cause;
- files changed and why;
- the regression test's before-fix failure and after-fix pass;
- focused and broader verification results;
- self-review findings and remaining risks;
- proposed local commit message containing the exact JIRA issue key, and exact files to stage.

Stop and wait for explicit commit approval. Adjust the fix if requested.

## Phase 6: Create a local commit only

After commit approval:

1. Recheck `git status` and the full diff.
2. Stage only the approved fix and test files by explicit path. Never use `git add .` or `git add -A`.
3. Confirm `.env`, unrelated changes, generated artifacts, and temporary attachments are not staged.
4. Follow the repository's commit convention while keeping the exact JIRA issue key in the subject. For Conventional Commits, prefer `<type>(<scope>): <JIRA-KEY> <concise fix summary>`, for example `fix(dbt): WARP-147650 修复Visual Model 重复退出确认`. If the repository has no convention, use `<JIRA-KEY>: <concise fix summary>`.
5. Create the commit locally and report its hash, subject, staged files, and post-commit worktree status.
6. End the workflow. Do not push or create a merge request.

## Failure handling

- JIRA 401: ask the user to check local `.env` credentials.
- JIRA 404: verify the issue key and permissions.
- Network failure: verify JIRA URL, VPN, and connectivity.
- Unstable or blocked reproduction: stop before root-cause claims and code edits.
- Test failure unrelated to the fix: separate baseline failures from regressions and report both.
- Commit failure: preserve the worktree and report the exact error; do not retry with destructive Git operations.
