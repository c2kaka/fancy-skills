---
name: ai-agent-framework-design-guide
description: Guide for writing AI Agent / Skill / Runtime framework design documents in Chinese-first style. Use when Codex needs to analyze an existing AI agent system or a proposed design, extract current architecture and constraints, define goals and boundaries, design layered architecture, routing and execution flows, configuration and interface models, runtime enhancement mechanisms, safety and fallback strategies, observability, rollout phases, and optionally include risks and open questions. Trigger for requests such as writing a framework design doc, architecture proposal, skill system design, runtime design, agent routing design, or turning scattered implementation notes into a formal architecture document.
---

# AI Agent Framework Design Guide

## Overview

Use this skill to turn code, design notes, and partial ideas into a formal framework design document for AI agent systems. Default to Chinese, keep terminology stable, and separate current-state facts from proposed architecture and open questions.

Read the references only as needed:

- Read [references/design-method.md](references/design-method.md) when the task starts from code, scattered notes, or conflicting existing docs.
- Read [references/document-outline.md](references/document-outline.md) when you need a ready-to-write structure for the final document.
- Read [references/section-writing-guide.md](references/section-writing-guide.md) when one section needs more depth or sharper framing.
- Read [references/example-patterns.md](references/example-patterns.md) when designing common Planner, Router, Skill, Runtime, Registry, Tool, or Operator boundaries.
- Read [references/quality-checklist.md](references/quality-checklist.md) before finalizing.

## Quick Start

1. Inspect the highest-signal artifacts first: existing design docs, README, manifests, router/planner code, skill registry code, runtime clients, core schemas, and configuration.
2. Reconstruct the current system before drafting the target design.
3. Compress the problem into design goals, scope boundaries, and compatibility constraints.
4. Write the document with explicit sections for architecture, flows, configuration, safety, rollout, and optional risks/open questions.
5. Self-review with [references/quality-checklist.md](references/quality-checklist.md).

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
- Prefer architecture goals such as consistency, explainability, extensibility, safety, or downgrade behavior over implementation task lists.

### 3. Define boundaries before internals

- For each major concept such as Planner, Router, Skill, Agent, Runtime, Registry, Tool, Operator, or Middleware, explain:
  - what it owns
  - what it depends on
  - what it is allowed to decide
  - what it explicitly does not do
- When two layers look similar, make the difference explicit. For example: route selection versus execution, skill registration versus runtime invocation, or context enrichment versus main business flow.
- Prefer negative boundaries when helpful, such as "Runtime skill does not determine top-level routing."

### 4. Design the static structure and dynamic flows

- Describe the layered architecture first, then the main call paths.
- Include at least one end-to-end execution path from user input to final result or runtime enrichment.
- Provide minimal viable configuration or schema examples when the design introduces structured plan/config models.
- Use Mermaid only when it improves understanding; otherwise use compact prose or bullet flows.
- Ensure every flow covers input, selection, execution, returned data, and fallback behavior.

### 5. Write the document as a formal design artifact

- Use [references/document-outline.md](references/document-outline.md) as the default structure unless the task is much smaller.
- Keep "current state", "proposed design", "required behavior", and "optional follow-up" visibly separated.
- Prefer concrete nouns over vague abstractions. Name the real modules, intents, protocols, schemas, and boundaries that matter.
- Support important claims with one of:
  - a source-derived fact
  - a schema snippet
  - a flow description
  - an explicit design rationale

### 6. Include rollout and risk framing

- End with a recommended rollout path such as `P0 / P1 / P2` or an equivalent staged plan.
- Add risks and open questions when the design depends on assumptions, unresolved ownership, unclear schemas, or behavior that still needs validation.
- If the user only asked for the design itself, keep risks and open questions brief but do not hide them.

## Writing Rules

- Default to Chinese. Keep the original English term in parentheses on first mention when it helps precision.
- Prefer "事实 -> 目标 -> 边界 -> 方案 -> 降级 -> 落地" over jumping straight to conclusions.
- Do not present implementation trivia as architecture. If a detail is only one possible implementation, label it accordingly.
- Do not invent components just to complete a diagram. If a layer is unknown, say it is unknown.
- Keep the document useful to both humans and future agents: concise, structured, and explicit about assumptions.

## Output Contract

Produce a framework design document that usually includes:

1. 设计目标
2. 现状依据
3. 总体架构
4. 核心配置或接口设计
5. 调用逻辑
6. 各类能力或 skill 处理流程
7. 运行时增强、上下文注入或参数透传
8. 安全、降级与可观测性
9. 推荐落地路径
10. 可选的风险与开放问题
11. 结论

Scale the outline to the task size, but avoid dropping the core sections on current-state evidence, boundaries, call flows, fallback behavior, and rollout order unless the request is intentionally narrow.

## Final Check

Before delivering, run through [references/quality-checklist.md](references/quality-checklist.md) and tighten anything that is vague, contradictory, or not yet grounded in the source context.
