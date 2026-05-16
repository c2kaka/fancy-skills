---
name: analyze-ai-agent-codebase
description: Analyze open-source AI agent, coding agent, agent runtime, and multi-agent repositories by extracting architecture layers, core type contracts, execution loops, tool pipelines, extension points, and design trade-offs. Use when Codex needs a reusable method to read unfamiliar agent codebases, compare frameworks, review an agent's source structure, or explain how to extend or reuse an existing AI agent project.
---

# Analyze AI Agent Codebase

## Overview

Analyze the repository as a system of boundaries, contracts, and trade-offs instead of reading it file by file. Prefer identifying the runtime shape first, then follow one or two critical data flows end to end, and finish by judging what the design optimizes for.

Read [references/pi-methodology.md](references/pi-methodology.md) when the repository looks architecture-heavy or when you need the full reasoning model behind this workflow. Read [references/analysis-template.md](references/analysis-template.md) when you need a ready-made report structure.

## Quick Triage

Classify the target before reading deeply:

- `runtime`: unified LLM calling layer, event stream, provider abstraction, loop engine
- `product shell`: CLI, IDE, Slack, web, RPC, or workflow host built on top of a runtime
- `framework`: reusable abstractions intended for other developers to compose
- `tooling layer`: tools, sandboxes, prompt assembly, config, resource loading, skills, extensions
- `mixed system`: one repo that contains two or more of the above

State which of these is dominant before continuing. That decision controls what to read first.

## Workflow

### 1. Draw the outer boundaries

Find the monorepo or package boundaries, the dependency direction, and the product surfaces. Prefer package manifests, workspace config, and a small dependency graph over browsing folders at random.

Answer these questions early:

- What are the layers?
- Which layers know about which others?
- What is core versus optional?
- Which package or folder is the narrow waist of the system?

### 2. Read the contracts before the implementations

Read types, interfaces, registries, and small coordinating modules first. In most agent codebases, the highest-signal files are:

- core message and event types
- provider or model registry
- agent loop or orchestrator
- stateful wrapper around the loop
- tool definition interface and tool execution pipeline
- extension or plugin contracts
- prompt assembly and configuration merge points

Do not begin with UI components, vendor-specific adapters, or generated catalogs unless the design question depends on them.

### 3. Follow one critical path end to end

Pick a single flow and trace it completely. Good starter paths:

- user request -> context assembly -> model call -> event stream -> final message
- tool declaration -> tool call -> validation -> execution -> result reinjection
- model selection -> registry lookup -> provider dispatch
- extension or plugin registration -> resource discovery -> runtime availability

Track the data shape at each hop. Prefer following one type name, event name, or callback interface across the repo with search.

### 4. Identify the three control surfaces

For agent systems, locate the places that control:

- what the agent can do
- what the agent is allowed to do
- what the agent gets to see

These are often implemented as:

- tool interfaces or executors
- permission hooks, policy filters, or sandboxes
- context transformers, prompt assembly, memory selection, or compaction

This separation usually reveals the real architecture faster than reading feature code.

### 5. Separate built-ins from composition

List which capabilities are first-class and which are composed from lower-level primitives. This is especially important for:

- sub-agents
- planning modes
- MCP or external tool bridges
- approval flows
- memory and retrieval
- skills, prompts, and extensions

If a feature is not built in, ask which lower-level callback, interface, or resource mechanism composes it.

### 6. Record trade-offs, not just mechanisms

For every important module, write:

- what problem it solves
- what it makes simpler
- what complexity it pushes elsewhere
- what alternatives the authors appear to have rejected

Prefer the format `got / gave up / why worth it`.

### 7. Trace the influence radius

For the feature or subsystem under study, map how far its reach extends across the codebase:

- which layers does it touch?
- which other modules read or write the same state?
- are there implicit dependencies such as config flags, message queues, scheduled jobs, or shared caches?
- does the same concept appear in multiple modules with different implementations?

Mark each crossing point with its risk level: same-layer / cross-layer / cross-module / cross-state. The wider the influence radius, the more carefully you should trace the full topology before drawing conclusions.

### 8. Check constraints and uncover decision history

Surface both the explicit and implicit rules the system follows. For the area under study, ask:

- which layering rules, boundary conventions, or coding norms does this code obey or violate?
- where does it rely on an unwritten convention that is not enforced by types or tests?
- what does the git history (blame, commit messages, linked PRs) reveal about why this approach was chosen over alternatives?
- which parts look intentionally inelegant — possibly a local optimum forced by business constraints, backward compatibility, or a previously failed attempt?

Treat past decisions as first-class context. Code that looks wrong in isolation may be correct given constraints you have not yet discovered.

### 9. Apply the explanation-power self-check

After studying a feature or subsystem, validate depth of understanding by answering three questions:

1. **Why was it done this way?** — intent, not just mechanism.
2. **What alternatives were considered or would be viable?** — trade-off awareness.
3. **Where is the weakest point or highest risk?** — boundary and failure-mode identification.

If you cannot answer all three, the analysis is incomplete. Go back and re-read the relevant contracts, git history, or cross-module dependencies before producing the final report.

### 10. End with reuse guidance

Conclude by mapping likely modification paths:

- prompt-only customization
- adding a tool or provider
- adding a new shell or host surface
- replacing storage, memory, or sandboxing
- changing the core loop or event model

Say clearly which changes are low-risk extension work versus deep architectural surgery.

## Reading Order

Use this order unless the repo structure makes it impossible:

1. workspace or package manifests
2. the main shared `types` or schema file
3. provider or model registry
4. loop engine or orchestrator
5. stateful wrapper or session manager
6. tool contracts and one representative tool
7. prompt, config, and resource loading
8. extension or plugin APIs
9. shell-specific code such as CLI, TUI, web, IDE, or Slack

## Anti-Patterns

Avoid these traps:

- starting from `main` and getting buried in bootstrapping noise
- reading every provider implementation before understanding the registry contract
- skipping generated files without asking why they exist
- mixing up code extensions with prompt-only skills
- treating UI code as architecture-defining when it is only a consumer
- summarizing modules without tracing any real end-to-end path
- stopping at "what the code does" without asking "why it was done this way"
- assuming inconsistency is a bug when it may be an intentional adaptation to different constraints
- ignoring git history — blame, commit messages, and linked PRs often reveal the real reason behind surprising design choices

## Output Contract

Produce a concise but architecture-aware report with:

1. system classification
2. layer map and dependency direction
3. core contracts and narrow waist files
4. one or two end-to-end execution paths
5. extension surfaces and safety boundaries
6. major trade-offs
7. influence radius and cross-cutting risk map
8. constraint violations or undocumented conventions discovered
9. key design decisions and their historical rationale
10. recommended entry points for future modification

When the user asks for depth, use [references/analysis-template.md](references/analysis-template.md) as the report skeleton.
