# Design Method

Use this reference when the request starts from code, scattered notes, mixed Chinese/English artifacts, or an existing system that already has partial routing and runtime behavior.

## 1. Collect the minimum viable evidence

Start from the shortest path to architecture truth:

1. Existing framework design docs, ADRs, or architecture notes
2. README and workspace manifests
3. Core type or schema files
4. Router, planner, registry, and runtime entrypoints
5. Configuration models and policy files
6. Representative execution paths

Avoid reading every implementation file before you know the main boundaries.

## 2. Build a fact table

Before proposing the target design, capture the current state in a compact fact table:

| Topic | Current fact | Source | Why it matters |
| --- | --- | --- | --- |
| Routing | Planner currently selects DAG intents via X | code/doc | Affects future handoff |
| Runtime | Context enrichment happens in Y | code/doc | Defines runtime boundary |
| Config | Skill metadata lives in Z | code/doc | Constrains schema design |

This helps prevent mixing current behavior with future intent.

## 3. Compress the real design problem

Turn raw observations into a small set of architecture questions:

- What is fragmented today?
- What needs one unified entry point?
- Which decisions should remain server-side?
- Which layers need clearer ownership?
- What must be compatible with the old path?

If the answer turns into a task list, rewrite it as design goals and constraints.

## 4. Draw the boundary matrix

Use a matrix like this when the system has Planner, Router, Skill, Agent, Runtime, Registry, Tool, or Operator layers:

| Layer | Owns | May read | May decide | Must not do |
| --- | --- | --- | --- | --- |
| Planner | Top-level routing | Skill metadata | Whether to enter a skill path | Execute arbitrary downstream internals |
| Runtime | Context enrichment | Registry, policies | Which runtime skill to call | Override top-level routing |

This is often the fastest way to remove ambiguity.

## 5. Design one static view and one dynamic view

Every framework design should explain both:

- Static structure: layers, modules, contracts, schemas, boundaries
- Dynamic behavior: what happens from input to output, including retries, replanning, fallback, and context injection

If the document has only static structure, it will miss real execution behavior. If it has only dynamic flows, it will miss ownership and extensibility.

## 6. Prefer minimal schemas over vague prose

When the design introduces structured inputs or plans, show a minimal example:

- frontmatter or YAML config
- JSON-like execution plan
- Pydantic-style data shape
- context object or shared data keys

Use examples to clarify boundaries, not to prescribe exact implementation unless the design requires that precision.

## 7. Separate three truth levels

Mark statements mentally or explicitly as one of:

- `现状事实`: derived from source artifacts
- `设计建议`: what this document proposes
- `开放问题`: what still needs a product, platform, or owner decision

Do not let open questions masquerade as settled architecture.

## 8. End with rollout, not just structure

A framework design is incomplete without execution strategy. Close with:

- what to normalize first
- what can be adapted later
- which steps unlock observability or safety earliest
- what can be piloted before full unification
