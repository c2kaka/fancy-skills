# fancy-skills

This repository stores reusable Agent skills and lightweight documentation for collaborating with AI tools on this corpus.

## Quick Start

Install a skill with:

```bash
npx skills add c2kaka/fancy-skills --path skills/<skill-name>
```

Replace `<skill-name>` with a folder under `skills/`, for example `ai-agent-framework-design-guide`, `analyze-ai-agent-codebase`, `bootstrap-ai-collab-infra`, `change-risk-review`, or `feature-intake`.

Then invoke in your agent terminal (or load the same skill name in your host's skill picker):

```
/ai-agent-framework-design-guide # Analyze an AI agent system and draft a Chinese-first framework design document
/analyze-ai-agent-codebase      # Methodically read an unfamiliar AI-agent codebase
/bootstrap-ai-collab-infra      # Scaffold layered docs, integration catalog, and CLAUDE.md for another repo
/change-risk-review             # Review git changes for risk classification before commit
/feature-intake                 # Reverse a single source of truth from HTML prototype + backend API docs, surfacing implicit business behavior as explicit human decisions

Your host may use `@` mentions, rules, or file paths instead of slash commands; the skill identity is the folder name under `skills/`.

## Structure

- `skills/`: each skill lives in its own folder
- `skills/<skill-name>/SKILL.md`: trigger metadata and workflow
- `skills/<skill-name>/agents/`: UI-facing agent metadata (optional)
- `skills/<skill-name>/references/`: load-on-demand reference material (optional)
- `docs/`: architecture panorama, integration surfaces, conceptual data model (`architecture.md`, `api-list.md`, `data-model.md`, `data-model-er.svg`)
- `.claude/skills/`: Claude-local helper skills (e.g. read-only docs drift reporting)

## Included Skills

- `ai-agent-framework-design-guide`: analyze existing AI agent / skill / runtime systems and write Chinese-first framework design documents with rollout phases, plus optional risks and open questions
- `analyze-ai-agent-codebase`: analyze open-source AI agent repositories through layers, contracts, execution loops, tools, and trade-offs
- `bootstrap-ai-collab-infra`: generate the layered-docs + API catalog + conceptual schema + `CLAUDE.md` + read-only `docs-auto-sync` playbook for arbitrary repositories
- `change-risk-review`: review git changes for behavior, protocol, and architecture risk before commit, then generate a classified commit message after user confirmation
- `feature-intake`: reverse-engineer a Feature Intake Spec from an HTML prototype + backend API docs, scan for five classes of implicit-behavior gaps, and force every gap to an explicit human decision or TODO before implementation

## Companion files

- [`CLAUDE.md`](CLAUDE.md): concise onboarding for AI assistants working in this repo
