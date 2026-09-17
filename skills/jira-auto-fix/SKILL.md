---
name: jira-auto-fix
description: Reproduce, diagnose, fix, test, self-review, and locally commit code for a JIRA bug using a skill-local .env and read-only JIRA REST access. Use when a user asks to fixbug or 修复 an issue such as JIRA-1234 and requires stable reproduction, a plain-language root-cause analysis walked through one concrete example, a change-locality check (whether the variation is contained at the boundary that should own it or leaks into many receivers), a plain-language solution explanation, explicit solution approval before edits, regression tests, and a local commit without push or merge request creation.
---

# JIRA Auto Fix

Fix one JIRA bug through a gated Codex workflow. Resolve resource paths relative to this `SKILL.md`; never assume the caller's working directory.

## Hard boundaries

- Treat JIRA access as read-only. Never edit, transition, comment on, or reassign the issue.
- Do not edit tracked project files or add tests until the user explicitly confirms the proposed solution.
- Do not claim stable reproduction from one observation. Require the same failure on at least two consecutive runs under the same controlled conditions. For intermittent bugs, record the sample size and failure rate and obtain user agreement on the reproduction threshold.
- Do not claim a root cause unless evidence connects it to the reproduced failure and rules out plausible alternatives.
- Do not widen the fix into a refactor in the name of locality. Locality analysis decides **where** the fix belongs; the fix itself stays minimal and coherent.
- Preserve pre-existing worktree changes. Never stash, reset, clean, or overwrite them automatically.
- Stop after creating a local commit. Never pull, fetch, rebase, push, force-push, or create a merge request.
- Require user confirmation at both gates: before code/test edits and before the local commit.
- Require the exact JIRA issue key to appear visibly in the local commit subject.

## Review summary contract

Present investigation results top-down so a reader who does not know the code can understand what went wrong, why, and what will change, before reading code-level evidence. Detailed writing rules and a complete worked example are in `references/review-packet-guide.md`; read it before writing the Phase 3 or Phase 5 packet.

### Plain-language rules

- Write in the user's language. Use business nouns and verbs first; introduce a code identifier only when it pins down the cause, and gloss any term the reader may not know the first time it appears.
- Explain every analysis and every solution through **one concrete example** taken from the actual reproduction: real input values, the real intermediate state the system produced, and the real output. Walk it as `情境 → 系统做了什么 → 为什么得到这个结果`, then map each step back to the code.
- Prefer short sentences with a specific subject and verb ("导出服务把空折扣当成 0 元" rather than "折扣处理存在缺陷"). Preserve conditions, causality, and uncertainty; do not trade accuracy for simplicity.
- Reuse the same example across the packet: the reproduction chain shows it failing, the root cause explains why, the solution shows the same input producing the correct result after the fix.

### Pyramid structure

Use this order for the Phase 3 approval packet. For a Chinese response, prefer exactly these headings: `Review 结论`, `1. 业务复现链路`, `2. 问题根因总结`, `3. 推荐解决方案`.

1. **Review 结论** — One plain-language sentence that classifies the finding (bug, implementation deviation, configuration/data problem, or not yet proven), states the user-visible impact, names the causal fault, and recommends the smallest coherent action. Add one sentence on change locality: whether the variation is contained where it belongs or leaks into many receivers.
2. **1. 业务复现链路** — The concrete example told as a causal chain: starting state and actor, exact inputs, system steps, expected result, actual result, and stable reproduction evidence (2+ matching failures).
3. **2. 问题根因总结** — Three parts, in order:
   - **一句话根因**: what the system misunderstood or skipped, in business terms.
   - **用例子讲清楚**: rerun the concrete example step by step, showing the exact point where the state becomes wrong and why the code makes that choice. Name the responsible code path and the decisive evidence, separate cause from symptom, and state which plausible alternatives were ruled out.
   - **变化的局部性**: identify the variation (the input, path, field, state, or format that differs between the good and bad case), name the boundary that should own it, list every receiver that currently guesses, converts, or checks it independently, and state the verdict: `已关住` (one owner, one missed spot) or `已泄漏` (many receivers each handle it). Follow `references/change-locality.md`.
4. **3. 推荐解决方案** — Four parts, in order:
   - **一句话方案**: what will change, in business terms ("让订单恢复时在一个地方统一补回折扣，而不是每个页面自己判断").
   - **修复后的同一个例子**: same input, new intermediate state, correct output.
   - **局部性检查**: which modules a change on this path should touch in theory, which files the proposal actually touches, and how many of those are receivers adding their own guard. If the fix would edit many receivers for the same reason, say so explicitly and either move the fix to the owning boundary or justify the local patch and record the structural signal.
   - **落地细节**: affected files or boundaries, why the change removes the cause, focused test plan, compatibility and operational risks, and rejected alternatives with brief reasons.
5. Put commands, logs, stack traces, and detailed evidence after the four decision sections. Do not make the reader reconstruct the conclusion from raw diagnostics.

### Mermaid guidance

Use Mermaid when it materially clarifies a chain that has at least three dependent steps, crosses modules or actors, branches between expected and actual behavior, or depends on state transitions or timing. Use `flowchart LR` for business/data flow, `sequenceDiagram` for actor ordering, and `stateDiagram-v2` for lifecycle defects. A locality diagram that shows one variation fanning out into many receivers is often the clearest way to show a leak. Label nodes in plain business language, mark the failure point visually, draw only evidence-backed steps, and keep one focused diagram per packet unless the business path and the code path are genuinely different. Examples are in `references/review-packet-guide.md`.

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
4. Record the concrete values of the failing case (input, intermediate state, output). They become the single example used throughout the review packet.
5. If the bug is intermittent, run a bounded sample, report attempts and failures, and do not label it stable without a repeatable trigger or a user-approved statistical threshold.
6. If reproduction is blocked by missing access, data, environment, or instructions, report the attempts and ask for the missing input. Do not guess a fix.

## Phase 3: Prove the root cause, check locality, and propose a solution

1. Trace the failing control flow and data flow from the reproduced signal to the responsible code.
2. Inspect callers, boundaries, state transitions, configuration, relevant tests, and `git log` or `git blame` where useful.
3. Form competing hypotheses and use evidence to eliminate them. Distinguish the root cause from downstream symptoms.
4. Run the locality analysis from `references/change-locality.md`:
   - name the variation that distinguishes the good case from the bad case;
   - name the boundary that should own it (the producer, adapter, parser, or normalizer where the variation enters the system);
   - search the codebase for every receiver that independently guesses, converts, or checks that variation, and count them;
   - decide whether the variation is contained (`已关住`) or leaked (`已泄漏`), and whether the reported bug is a single missed spot or one instance of a systemic leak.
5. Define the smallest coherent fix. When the variation is leaked, prefer closing it at the owning boundary if that change is small and coherent; otherwise patch the missed receiver and record the structural signal explicitly. State the locality budget: which modules a change on this path should touch in theory versus which files the fix touches in practice.
6. Present the approval packet using the `Review summary contract`. Include the JIRA key and summary, stable reproduction conditions and 2+ matching failures, the concrete example, the plain-language root cause, the locality verdict, the plain-language solution with the same example after the fix, the locality check, alternatives, test plan, and risks inside the appropriate pyramid section.
7. Stop and wait. Continue only after the user explicitly confirms the solution. If the user requests changes, revise the analysis and request confirmation again.

## Phase 4: Add the regression test, then fix

After solution approval:

1. Add the narrowest regression test that expresses the reproduced failure, using the same concrete example where practical.
2. Run the new test before changing production code and capture that it fails for the expected reason. If this ordering is technically impossible, explain why and agree on equivalent evidence before proceeding.
3. Implement the approved minimal fix. Do not include unrelated refactors.
4. Compare the actual diff against the locality budget stated in the packet. If the fix is spreading into more receivers than planned, stop and report before continuing; this usually means the variation is not closed where it should be.
5. Run the regression test and confirm it passes.
6. Run relevant boundary, error, and existing regression checks in proportion to risk. Use the repository's actual build and test commands rather than assuming Maven.
7. Review the complete diff against `references/code-review-checklist.md`.

## Phase 5: Report and request commit approval

Reuse the top-down `Review summary contract`, but change **3. 推荐解决方案** to **3. 已实施方案**. Lead with the outcome in plain language, then show the same concrete example as before/after behavior, the confirmed root cause and fix mapping, the locality check against the actual diff (planned versus touched files, receivers edited and why), files changed and why, the regression test's before-fix failure and after-fix pass, focused and broader verification, self-review findings, remaining risks including any recorded structural signal, the proposed local commit message containing the exact JIRA issue key, and the exact files to stage.

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
- Locality search inconclusive (dynamic dispatch, reflection, generated code): report the receivers found, state that the count is a lower bound, and do not label the variation `已关住` on incomplete evidence.
- Test failure unrelated to the fix: separate baseline failures from regressions and report both.
- Commit failure: preserve the worktree and report the exact error; do not retry with destructive Git operations.
