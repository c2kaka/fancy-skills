# fancy-skills — AI collaboration brief

## 1. Project positioning

`fancy-skills` is a **small, Git-versioned library of Agent skills** (Markdown workflows plus optional YAML bindings and reference docs). It ships **no runtime server**, **no database**, and **no REST API**—value is in portable instructions consumed by Cursor, Claude Code, Codex-style hosts, or similar agent shells.

## 2. Core architecture

Three conceptual planes work together:

1. **Consumption plane** — Host products load `SKILL.md` (and sometimes `agents/*.yaml`) to decide when and how to run a workflow.
2. **Package plane** — Each skill under `skills/<name>/` bundles manifest (`SKILL.md` frontmatter), optional UI hooks (`agents/`), and optional deep references (`references/`).
3. **Documentation plane** — Root `README.md` plus `docs/` explain repo-wide conventions and conceptual schemas so humans and AI share one map.

See layered and dependency diagrams in `docs/architecture.md`.

## 3. Key modules

| Path | Role |
|------|------|
| `skills/analyze-ai-agent-codebase/` | Methodology skill for reading AI agent codebases; primary artifact is `SKILL.md`, with deferred templates under `references/`. |
| `skills/bootstrap-ai-collab-infra/` | Meta-playbook skill that prescribes how to author `docs/*`, `CLAUDE.md`, and the read-only `docs-auto-sync` helper for other repositories. |
| `skills/*/agents/` | Thin YAML descriptors (`display_name`, `default_prompt`) for hosts that substitute `$<skill-name>` tokens. |
| `docs/` | Architecture narrative, integration surface catalog, conceptual data model + ER SVG. |
| `.claude/skills/docs-auto-sync/` | Read-only drift checker skill comparing docs to filesystem facts (report-only). |

## 4. Key conventions

- **Skill identity**: Folder name under `skills/` SHOULD match `name` in `SKILL.md` frontmatter for predictable discovery.
- **Description field**: Third-person, ends with explicit **“Use when …”** triggers—this is how agents choose the skill.
- **Progressive disclosure**: Keep `SKILL.md` lean; move long methodology to `references/` and link.
- **No fictional APIs**: Do not document REST/OpenAPI for this repo unless an actual server is added.

## 5. How to run / use

1. Clone the repository.
2. Point your Agent host at a skill folder or install via your platform’s skill mechanism.
3. For analysis methodology, invoke **`analyze-ai-agent-codebase`** when exploring unfamiliar agent repositories.
4. To regenerate conceptual docs for *another* codebase using the same playbook, use skill **`bootstrap-ai-collab-infra`** from `skills/bootstrap-ai-collab-infra/SKILL.md`.
5. After substantive edits, optionally run **`docs-auto-sync`** (read-only) to list documentation drift.

There is **nothing to `npm install` or `docker compose up`** in this repository today.

## 6. Guardrails / forbidden zones

待开发人员补充

## 7. Historical baggage / known debt

待开发人员补充
