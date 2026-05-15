---
name: bootstrap-ai-collab-infra
description: Bootstraps an AI-human collaboration documentation kit for any codebase by authoring layered architecture diagrams, integration surface catalogs, conceptual data models with ER SVG, reconciling inconsistencies, generating root CLAUDE.md, and adding a read-only docs drift skill. Use when the user requests full AI collaboration infrastructure, automated documentation bootstrap, architecture plus API catalog plus data model deliverables, or repeating the fancy-skills documentation playbook on another repository.
---

# Bootstrap AI Collaboration Infrastructure

## Quick start

1. Read the repository README and package manifests to classify the system (monolith, monorepo, skills-only repo, etc.).
2. Execute the workflows below **in order**, self-reviewing each artifact before continuing.
3. Finish with a **summary** listing outputs, contents, and human follow-ups.

## Workflows

### Phase A — Architecture panorama (`docs/architecture.md`)

Create or overwrite `docs/architecture.md` containing **three Mermaid diagrams**:

1. **Layered architecture** — top-to-bottom or LR chart; each core module annotated with **one-line responsibility** table.
2. **Internal dependency graph** — directed edges between real modules/packages. **Mark cyclic dependencies** using Mermaid `style <node> fill:#ffcdd2` (only on nodes inside cycles). If none, state that explicitly in prose beside the diagram.
3. **Tri-class diagram** — partition **internal artifacts**, **middleware/tooling**, and **external APIs/services**; use subgraphs.

Adapt labeling when the project is documentation-only or lacks HTTP servers—do **not** invent REST layers.

Optional compatibility path: also write `docs/acchitecture.md` as a pointer if teammates rely on the historic typo filename.

### Phase B — Interfaces & conceptual schema

1. `docs/api-list.md` — Group by module. Tag each surface **External** vs **Internal**. Use REST/OpenAPI rows **only** if real endpoints exist; otherwise document RPC, GraphQL, CLI, webhooks, or file-based contracts truthfully.
2. `docs/data-model.md` — Ground narrative in the **actual persistence layer** (database, ORM schema, or explicit file schema). If no DB, declare authoritative stores (e.g., Markdown frontmatter) and integrity rules.
3. `docs/data-model-er.svg` — SVG entity-relationship diagram reflecting `data-model.md` (boxes + cardinalities + legend).

### Phase C — Reconciliation loop

1. Diff claims across `api-list.md` and `data-model.md` (names, entities, endpoints vs tables).
2. Fix doc files until **no unresolved contradictions** remain; note deliberate exceptions inline with rationale.
3. Re-open `architecture.md` and align module naming with the two docs.

### Phase D — Root `CLAUDE.md`

Generate `CLAUDE.md` at repo root **without duplicating** full docs content (<300 lines):

1. Project positioning  
2. Core architecture (pointer tone, not paste)  
3. Key modules  
4. Key conventions  
5. How to run/build/test  

Reserve sections **“禁区 / Guardrails”** and **“历史包袱 / Debt”** with placeholder text: `待开发人员补充`.

### Phase E — Highest priority follow-up skill (`docs-auto-sync`)

Create `.claude/skills/docs-auto-sync/SKILL.md` that:

- Declares **`allowed-tools: Read, Grep`** (read-only)
- Runs a deterministic checklist comparing `docs/*` to repo facts
- **Reports only** — no auto-fix commands

### Phase F — Session summary

Deliver a final markdown summary covering:

- Each file touched
- One-sentence description of its contents
- Items needing **human confirmation**
- Judgment calls made when ambiguous

## Autonomous execution principles

- Self-review each phase; redraw diagrams if unclear or incomplete.
- Prefer faithful descriptions over imagined infrastructure.
- Document assumptions explicitly in the Phase F summary.

## Review checklist

- [ ] Description includes triggers (“Use when…”)
- [ ] `SKILL.md` stays concise; split references only when >100 lines repetitive detail
- [ ] No time-sensitive marketing claims
- [ ] Examples mention both HTTP-heavy and docs-only repos
