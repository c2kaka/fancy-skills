---
name: change-risk-review
description: Use when Codex needs to review current git changes for AI-coding risk, summarize behavior changes, affected historical features, protocol/schema changes, golden-test evidence, and uncertainty before commit; also use when the user confirms the review and asks Codex to commit, so the commit message includes concrete change categories such as tuning, behavior change, protocol change, or architecture change with PR-review-ready details.
---

# Change Risk Review

## Overview

Use this skill as a lightweight safety gate for fast AI-assisted development. It turns a raw git diff into a focused risk review, then, only after user confirmation, helps create a commit message that classifies the change and describes the concrete impact for PR reviewers.

Default to Chinese output unless the repository or user request clearly prefers English.

## Workflow

### 1. Inspect Git State First

Use focused git commands before judging the change:

- `git status --short`
- `git diff --stat`
- `git diff -- <focused paths>` for changed source, tests, docs, configs, schemas, and prompts
- `git diff --cached` if files are already staged
- `git log --oneline -n 5` only when recent context helps classify risk

Do not assume unstaged changes are yours. If unrelated files are dirty, isolate the review to files relevant to the user's request and call out unrelated changes briefly.

## Review Output

Lead with risks and evidence, not a generic summary. Cover these five required questions:

1. 改了哪些行为
   - Describe user-visible behavior, agent routing behavior, prompt/LLM behavior, state transitions, persistence behavior, or error-handling behavior that changed.

2. 可能影响哪些历史功能
   - Name likely affected existing flows, especially planner routing, skill routing, session memory, resume/rerun, rollback, streaming, frontend protocol payloads, and golden scenarios.

3. 新增/修改了哪些协议字段
   - Check JSON payloads, message `additional_kwargs`, session/memory fields, config keys, API parameters, frontend-rendered markdown/custom markup, database fields, and enum/status values.
   - If no protocol field changed, say so explicitly.

4. 跑了哪些 golden tests
   - List exact commands or state that no tests were run.
   - Distinguish golden/regression tests from incidental tests.
   - If no golden tests exist, recommend the smallest scenario that should become one.

5. 哪些地方是 AI 不确定的
   - Identify assumptions, unverified compatibility, missing tests, ambiguous ownership, migration uncertainty, or areas where behavior depends on prompts/model output.

Use this structure:

```markdown
**风险 Review**

- 行为变化：...
- 可能影响的历史功能：...
- 协议/字段变化：...
- Golden tests：...
- AI 不确定点：...

**建议**
- ...
```

## Risk Classification

Classify the change using one or more categories:

| 分类 | 触发条件 |
| --- | --- |
| 调优 | prompt、阈值、排序、打分、策略微调；目标是不改变协议和主流程契约 |
| 行为变更 | 用户可见输出、路由结果、错误处理、恢复/重跑行为、默认策略发生变化 |
| 协议变更 | JSON、message、session、memory、config、API 参数、enum/status、frontend payload 字段变化 |
| 架构变更 | Planner/Skill/Action/Runtime/Memory/Tool 的责任边界、调用链、生命周期或状态主控权变化 |

If a change fits multiple categories, keep all relevant categories. Do not down-classify a protocol or architecture change as tuning just because the diff is small.

## Commit Gate

Do not create a commit during the first review pass.

Only help commit when both are true:

- The user has confirmed the review is acceptable or has accepted the residual risks.
- The user explicitly asks Codex to commit.

Before committing, verify the staged set:

- If nothing is staged, ask whether to stage the reviewed files or stage them if the user already requested that exact scope.
- If unrelated files are staged, stop and ask for confirmation before including them.

## Commit Message Requirements

The commit message must include both classification and concrete change details. The notes/body should be useful to PR reviewers without reading the full diff.

Recommended format:

```text
<type>: <short summary>

变更分类：
- 调优：<具体说明 prompt/阈值/策略如何变化；没有则删除此行>
- 行为变更：<具体说明用户可见行为或 agent 行为如何变化；没有则删除此行>
- 协议变更：<具体说明字段、payload、状态或兼容策略如何变化；没有则删除此行>
- 架构变更：<具体说明责任边界、调用链、生命周期或状态主控权如何变化；没有则删除此行>

影响面：
- <列出可能受影响的历史功能、模块、链路或 golden scenarios>

验证：
- <列出已运行测试命令或说明未运行及原因>

AI 不确定点：
- <列出剩余假设、未覆盖风险；没有则写“无明确残留不确定点”>
```

Examples:

```text
feat: route action skills through session orchestrator

变更分类：
- 行为变更：Planner skill 命中 DATA_QUERY 后改为通过统一 ticket 执行，避免绕过 child session 主链。
- 协议变更：child message 增加 control/action_payload 分层读取逻辑，并保留旧字段兼容读取。
- 架构变更：parent-child session 主控从 Planner/DataQueryAction 分散写入收敛到 ActionSessionOrchestrator。

影响面：
- 影响 Planner skill、DATA_QUERY resume/rerun、artifact rollback、parent action_link 状态回写。

验证：
- uv run pytest tests/planner_agent/test_data_query_resume.py -q
- uv run pytest tests/planner_agent/test_planner_skills.py -q

AI 不确定点：
- BUILD/GOVERNANCE 的 round 级恢复还缺少端到端 golden scenario。
```

```text
tune: adjust planner skill routing threshold

变更分类：
- 调优：提高 skill route 置信度阈值，减少低置信度 prompt-only skill 误命中。
- 行为变更：边界输入更可能回退到普通 Planner 路由。

影响面：
- 可能影响 skill 命中率、普通规划兜底链路、历史 prompt-only skill 场景。

验证：
- uv run pytest tests/planner_agent/test_planner_skills.py -q

AI 不确定点：
- 未用真实线上问题集回放阈值变化。
```

Keep the first line concise. Put detailed classification in the body, not only in the subject.

## Final Response After Commit

After a successful commit, summarize:

- commit hash
- classification categories
- tests run
- any residual risk

If the commit did not happen, state exactly why.
