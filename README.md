# fancy-skills

This repository stores reusable Agent skills and lightweight documentation for collaborating with AI tools on this corpus.

## Structure

- `skills/`: each skill lives in its own folder
- `skills/<skill-name>/SKILL.md`: trigger metadata and workflow
- `skills/<skill-name>/agents/`: UI-facing agent metadata (optional)
- `skills/<skill-name>/references/`: load-on-demand reference material (optional)
- `docs/`: architecture panorama, integration surfaces, conceptual data model (`architecture.md`, `api-list.md`, `data-model.md`, `data-model-er.svg`)
- `.claude/skills/`: Claude-local helper skills (e.g. read-only docs drift reporting)

## Included Skills

- `analyze-ai-agent-codebase`: analyze open-source AI agent repositories through layers, contracts, execution loops, tools, and trade-offs
- `bootstrap-ai-collab-infra`: generate the layered-docs + API catalog + conceptual schema + `CLAUDE.md` + read-only `docs-auto-sync` playbook for arbitrary repositories

## Companion files

- [`CLAUDE.md`](CLAUDE.md): concise onboarding for AI assistants working in this repo
