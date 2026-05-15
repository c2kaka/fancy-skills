# PI-Derived Methodology For Reading Agent Code

This note extracts reusable source-reading methodology from the online book [pi 的设计艺术](https://zhanghandong.github.io/pi-book/print.html). The goal is not to memorize `pi`, but to reuse its reading discipline on other open-source AI agent systems.

## Core Principle

Read by design question, not by directory order.

High-value questions look like:

- Why is the main loop stateful or stateless?
- Why are tools structured as a pipeline instead of direct calls?
- Why are prompts assembled dynamically instead of stored as one string?
- Why are some capabilities implemented as code while others are plain documents?
- Why are certain features built in while others are composed from lower-level primitives?

When you read through design questions, source files become evidence instead of the reading plan.

## The Reusable Reading Model

### 1. Find the narrow waist

Most strong agent codebases have a small set of files that the rest of the system bends around:

- shared type definitions
- registry modules
- the core loop or orchestrator
- the event stream contract
- tool interfaces

Read these first. They reveal the shape of the whole system with less noise than entrypoints or shell code.

### 2. Follow types as architecture

Treat types, schemas, and event unions as architecture documents.

A productive pattern is:

1. find one high-value type
2. search for where it is created
3. search for where it is transformed
4. search for where it crosses a layer boundary
5. search for where it becomes vendor-specific or UI-specific

This turns source reading from browsing into tracing.

### 3. Separate core logic from consumers

The book repeatedly distinguishes between design-defining code and design-consuming code.

Usually read later:

- TUI and editor components
- web components
- platform adapters
- large provider-specific implementations
- generated model catalogs

Usually read earlier:

- loop engine
- type contracts
- dispatch registries
- tool pipeline
- config merge logic
- prompt assembly

The question is not "is this file important?" but "does this file define the system, or merely consume a decision made elsewhere?"

### 4. Trace one path completely

Do not stop at summaries. Pick one path and finish it.

Examples:

- request -> context -> model dispatch -> stream -> result
- tool schema -> tool call -> prepare -> execute -> finalize -> reinjection
- user config -> merged config -> effective runtime policy

One complete path teaches more than ten partial file summaries.

### 5. Read trade-offs as first-class artifacts

The book's most reusable habit is to ask of each subsystem:

- what did this buy?
- what did it cost?
- which complexity moved up or down the stack?

When analyzing another repo, try to write three lines per major module:

- `got:`
- `gave up:`
- `worth it because:`

If you cannot state the trade-off, you probably only understood the surface implementation.

## High-Signal Targets In AI Agent Repos

### Layering and dependency direction

Look for:

- package manifests
- workspace definitions
- exports maps
- subpath exports
- runtime-specific packages

Ask:

- can lower layers import higher layers?
- is the boundary enforced by packages or just convention?
- where is the narrowest reusable core?

### Loop and state split

Many agent systems split into:

- a pure or mostly pure loop
- a stateful shell that owns history, cancellation, and subscriptions

If this split exists, understand it early. It often determines how extensible the system is.

### Tool execution pipeline

Do not assume "tools" mean function calls.

Inspect whether the system distinguishes:

- validation or preparation
- execution
- auditing, mutation, or result normalization
- permission checks
- parallel versus sequential semantics

This area usually reveals the project's safety model.

### Prompt and context assembly

Agent behavior often comes more from assembly logic than from a single prompt file.

Trace:

- base prompt
- repository-specific overlays
- user overrides
- skill or extension injection
- dynamic runtime hints
- memory or compaction inputs

### Built-ins versus composed features

One of the strongest questions in the book is whether a feature is first-class or composed.

Apply it to:

- sub-agents
- planning
- approvals
- memory
- MCP bridges
- skills
- resource loading

When a feature is composed instead of built in, identify the lower-level primitive that makes it possible.

## Common Reading Mistakes

### Mistake 1: starting from startup

Entrypoints are often full of bootstrapping noise. Use them later to confirm wiring, not earlier to infer architecture.

### Mistake 2: over-reading adapters

If the repo supports many providers or hosts, read one representative implementation after you understand the contract. The registry matters more than the tenth adapter.

### Mistake 3: skipping generated files without asking why

A generated file may still be a major architectural clue. Understand why it exists even if you never read its contents line by line.

### Mistake 4: collapsing extension mechanisms together

Different systems often have:

- code extensions
- prompt overlays
- config files
- document-based skills
- external tools

Keep their capability boundaries separate.

### Mistake 5: describing instead of judging

"This file parses config" is too shallow. Better:

"This file centralizes multi-level config override, which buys predictability at the cost of more indirect runtime behavior."

## A Reusable Analysis Sequence

Use this sequence on unfamiliar agent repos:

1. classify the system
2. draw layers and dependency direction
3. find the narrow waist files
4. read contracts before implementations
5. trace one request path and one tool path end to end
6. identify control surfaces for capability, permission, and context
7. separate built-ins from composed features
8. write trade-offs and extension paths
9. judge where to customize without breaking the core

## What To Borrow Specifically From This Book

Borrow these habits directly:

- read architecture through a small number of anchor files
- use types as the shortest path to understanding data flow
- treat event streams and registries as core abstractions
- distinguish inner runtime from outer product shell
- analyze what is externalized on purpose
- end every subsystem reading with a trade-off judgment

Those habits transfer cleanly to other AI agent repos even when the language, framework, or product surface is different.
