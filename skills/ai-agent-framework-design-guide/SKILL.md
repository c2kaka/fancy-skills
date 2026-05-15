---
name: ai-agent-framework-design-guide
description: Guide for writing or reviewing AI Agent / Skill / Runtime framework design documents in Chinese-first style. Use when Codex needs to analyze an existing AI agent system or a proposed design, extract current architecture and constraints, define goals and boundaries, design layered architecture, routing and execution flows, configuration and interface models, runtime enhancement mechanisms, safety and fallback strategies, observability, rollout phases, review checklists, and risks/open questions. Trigger for requests such as writing a framework design doc, reviewing a design guide, architecture proposal, skill system design, runtime design, agent routing design, or turning scattered implementation notes into a formal architecture or review document.
---

# AI Agent Framework Design Guide

## Overview

Use this skill to turn code, design notes, and partial ideas into a formal framework design or design-review document for AI agent systems. Default to Chinese, keep terminology stable, and separate current-state facts, proposed architecture, review criteria, and open questions.

Read the references only as needed:

- Read [references/design-method.md](references/design-method.md) when the task starts from code, scattered notes, or conflicting existing docs.
- Read [references/document-outline.md](references/document-outline.md) when you need a ready-to-write structure for the final document.
- Read [references/section-writing-guide.md](references/section-writing-guide.md) when one section needs more depth or sharper framing.
- Read [references/example-patterns.md](references/example-patterns.md) when designing common Planner, Router, Skill, Runtime, Registry, Tool, or Operator boundaries.
- Read [references/quality-checklist.md](references/quality-checklist.md) before finalizing.

## Quick Start

1. Inspect the highest-signal artifacts first: existing design docs, README, manifests, router/planner code, skill registry code, runtime clients, core schemas, and configuration.
2. Reconstruct the current system before drafting the target design.
3. Identify the document type: design proposal, design review guide, implementation plan, migration plan, or mixed artifact. Do not let a review guide become a disguised design proposal without explicit review questions and evidence requirements.
4. Compress the problem into design goals, scope boundaries, compatibility constraints, and terminology.
5. Write the document with explicit sections for architecture, flows, configuration, lifecycle, safety, rollout, and optional risks/open questions.
6. Self-review with [references/quality-checklist.md](references/quality-checklist.md).

## Workflow

### 1. Reconstruct the current state before proposing the target design

- Prefer source artifacts over assumptions. Gather real modules, execution paths, configuration models, schemas, integration points, and constraints before drafting the design.
- Distinguish clearly between:
  - current facts from code or documents
  - new design decisions introduced in this document
  - unresolved questions or assumptions
- If sources conflict, record the mismatch explicitly instead of silently normalizing it.

### 2. Define the design problem sharply

- Write 3 to 7 design goals that explain what the framework is trying to unify or improve.
- Call out what is in scope and what is intentionally out of scope.
- Identify compatibility constraints, migration pressure, and any existing execution or routing logic that must continue to work.
- Define the document's job before writing details:
  - design proposal: state decisions and rationale
  - review guide: state review questions, required evidence, and decision points
  - migration plan: state phases, invariants, and rollback paths
- Prefer architecture goals such as consistency, explainability, extensibility, safety, or downgrade behavior over implementation task lists.

### 3. Define terms and boundaries before internals

- Define key terms before using them repeatedly. For agent/runtime designs, check whether the document needs explicit definitions for:
  - control plane versus execution/data plane
  - route, plan, skill, action, tool, operator, runtime, registry, memory, session
  - round versus step, task versus run, parent versus child session
  - continuation modes such as `new`, `reuse`, `resume`, `rerun`, `rollback`
- If a field, state, or identifier appears in multiple sections, define its legal values, producer, consumer, trust level, and lifecycle.
- Separate orthogonal classification axes. For example, do not mix "skill shape" (`prompt-only skill`, `action skill`) with "action domain" (`DATA_QUERY`, `BUILD`, `GOVERNANCE`) as peers unless a matrix explains the cross-product.

- For each major concept such as Planner, Router, Skill, Agent, Runtime, Registry, Tool, Operator, or Middleware, explain:
  - what it owns
  - what it depends on
  - what it is allowed to decide
  - what it explicitly does not do
- For helper components shown in a diagram, such as Policy, Recorder, Adapter, Store, or Orchestrator, include at least one sentence on responsibility and lifecycle. If the component is only an implementation detail, label it as such or omit it from the main architecture diagram.
- When two layers look similar, make the difference explicit. For example: route selection versus execution, skill registration versus runtime invocation, or context enrichment versus main business flow.
- Prefer negative boundaries when helpful, such as "Runtime skill does not determine top-level routing."

### 4. Design the static structure and dynamic flows

- Describe the layered architecture first, then the main call paths.
- Show current-state flows separately from target-state flows when migration is involved. Avoid labeling a target flow as an "old flow" if it already includes new components.
- Include at least one end-to-end execution path from user input to final result or runtime enrichment.
- Provide minimal viable configuration or schema examples when the design introduces structured plan/config models.
- For stateful designs, include lifecycle and idempotency rules for tickets, sessions, runs, tasks, messages, or other durable control objects. Cover creation, consumption, repeated calls, finalization, archive/read-only state, and late events.
- Use Mermaid only when it improves understanding; otherwise use compact prose or bullet flows.
- Ensure every flow covers input, selection, validation, execution, recording, returned data, finalization, and fallback behavior.
- When a diagram has bidirectional arrows, explain whether they represent direct calls, callbacks, events, or ownership. Call out coupling risks when a component both invokes and reports back to another component.

### 5. Write the document as a formal design artifact

- Use [references/document-outline.md](references/document-outline.md) as the default structure unless the task is much smaller.
- Keep "current state", "proposed design", "required behavior", and "optional follow-up" visibly separated.
- For review guides, keep "design summary", "review questions", "required evidence", and "open decisions" visibly separated.
- Prefer concrete nouns over vague abstractions. Name the real modules, intents, protocols, schemas, and boundaries that matter.
- Support important claims with one of:
  - a source-derived fact
  - a schema snippet
  - a flow description
  - an explicit design rationale
- For protocol or payload changes, explain compatibility rules:
  - new versus old structure
  - read precedence
  - write/double-write behavior
  - conflict resolution
  - migration exit condition
- For security-sensitive or model-influenced fields, state which fields are server-controlled, model-controlled, runtime-derived, or untrusted. Explicitly say which inputs must be ignored or revalidated even if they appear in history, runtime state, or legacy payloads.

### 6. Include rollout and risk framing

- End with a recommended rollout path such as `P0 / P1 / P2` or an equivalent staged plan.
- Add risks and open questions when the design depends on assumptions, unresolved ownership, unclear schemas, or behavior that still needs validation.
- Include review evidence for high-risk changes. Evidence can be focused tests, integration scenarios, protocol examples, observability fields, migration dry-runs, or failure-mode walkthroughs.
- Treat downgrade behavior carefully: if partial writes or degraded memory are allowed, distinguish controlled degradation from uncontrolled corruption, and specify how later reuse avoids polluted state.
- If the user only asked for the design itself, keep risks and open questions brief but do not hide them.

## Writing Rules

- Default to Chinese. Keep the original English term in parentheses on first mention when it helps precision.
- Prefer "事实 -> 目标 -> 边界 -> 方案 -> 降级 -> 落地" over jumping straight to conclusions.
- Do not present implementation trivia as architecture. If a detail is only one possible implementation, label it accordingly.
- Do not invent components just to complete a diagram. If a layer is unknown, say it is unknown.
- Avoid "review by agreement" phrasing alone, such as only asking whether the team agrees with a direction. Add the concrete evidence, invariants, and failure cases that must be checked.
- Keep the document useful to both humans and future agents: concise, structured, and explicit about assumptions.

## Output Contract

Produce a framework design document that usually includes:

1. 设计目标
2. 现状依据
3. 总体架构
4. 核心配置或接口设计
5. 调用逻辑
6. 各类能力或 skill 处理流程
7. 生命周期、状态机与幂等规则
8. 运行时增强、上下文注入或参数透传
9. 安全、降级与可观测性
10. 推荐落地路径
11. 可选的风险、开放问题与评审证据
12. 结论

For a design review guide, usually include:

1. 评审目标与使用方式
2. 现状依据与关键术语
3. 当前问题的本质判断
4. 总体架构与职责边界
5. 核心接口、协议与生命周期
6. 调用逻辑与责任流
7. 能力矩阵或分类维度
8. 安全、降级、状态机与可观测性
9. 推荐落地路径
10. 风险、开放问题与评审证据
11. 评审建议清单
12. 结论

Scale the outline to the task size, but avoid dropping the core sections on current-state evidence, terminology, boundaries, call flows, lifecycle/finalization, fallback behavior, observability, and rollout order unless the request is intentionally narrow.

## Final Check

Before delivering, run through [references/quality-checklist.md](references/quality-checklist.md) and tighten anything that is vague, contradictory, or not yet grounded in the source context.

Also check for these common structural failures:

- A review guide mostly repeats a design proposal but lacks review questions or required evidence.
- A diagram contains components that are not explained in text.
- Two orthogonal dimensions are presented as one hierarchy instead of a matrix.
- A field or state is used in several sections without legal values or lifecycle.
- A "current flow" already includes proposed components.
- A degradation rule permits partial writes without explaining how polluted state is detected or avoided later.
- A bidirectional runtime dependency appears without an interface or event boundary.
- A security rule bans a field that is not in the schema without explaining where the untrusted value could enter.
- Observability fields appear without generation time, cardinality, or relation to existing identifiers.
