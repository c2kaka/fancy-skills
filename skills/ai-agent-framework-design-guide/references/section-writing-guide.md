# Section Writing Guide

Use this reference when one section feels generic or under-specified.

## 1. 设计目标

Write goals as architecture outcomes, not implementation chores.

Good examples:

- 统一 Planner、Skill 和 Runtime 的职责边界
- 让运行时增强能力可注册、可降级、可审计
- 限制 LLM 只能选择业务参数，不能绕过服务端执行模板

Weak examples:

- 新增三个类
- 改一下接口
- 补日志

## 2. 现状依据

This section should answer:

- 当前有哪些真实机制已经存在
- 它们分别负责什么
- 设计为什么不能从零开始
- 当前冲突、割裂或重复在哪里

Use concrete names from the source artifacts. If the system already has a `SkillRouterAction` or `RuntimeClient`, name it directly instead of saying "some router" or "an execution layer."

## 3. 总体架构

This section should show:

- the top-level layers
- the dependency direction
- the handoff points
- which boundaries are authoritative

Keep each layer description short and ownership-focused. If there is one key diagram, this is usually the best place for it.

## 4. 核心配置或接口设计

This section should include:

- a minimal config example
- field meanings
- validation constraints
- what the model may choose versus what the server must enforce

Prefer a small YAML or JSON example over long abstract prose.

## 5. 调用逻辑

This section should read like an execution story:

1. 输入如何进入系统
2. 谁先判断
3. 谁构建 plan 或参数
4. 谁执行
5. 谁记录轨迹
6. 什么情况下继续、停止或降级

Use sequence-style prose or Mermaid when the path is long.

## 6. 各类能力或 Skill 处理流程

When the design has multiple capability types, explain them separately. For example:

- Planner skill: solve multi-step orchestration
- Agent skill: solve single-agent entry and parameter adaptation
- Runtime skill: solve context enrichment without changing top-level routing

This is often where the document becomes convincing, because it proves that the categories are not redundant.

## 7. 运行时增强、参数透传与上下文注入

Focus on:

- which context is created
- which component owns it
- where it is injected
- what can be trusted
- what must be revalidated

This section is also a good place to define shared data keys, context references, or trace payloads.

## 8. 安全、降级与可观测性

Do not treat this as an appendix. It should state:

- what the model is forbidden to control
- what is validated by the server
- what happens when matching, routing, runtime selection, or package APIs fail
- which fields must appear in logs or user-visible traces

## 9. 推荐落地路径

Good rollout sections are ordered by dependency and leverage:

- P0 normalizes contracts and validation
- P1 adapts main execution paths without deleting compatibility layers too early
- P2 unifies observability, registry, UI, and evaluation

Avoid phases that are just chronological edits with no architecture logic.

## 10. 风险与开放问题

Only include real issues that affect correctness, ownership, migration, or explainability. Keep "risk" and "open question" distinct:

- Risk: something likely to go wrong if the design is implemented as written
- Open question: something that must be decided before the design is complete
