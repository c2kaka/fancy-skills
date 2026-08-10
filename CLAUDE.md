# fancy-skills — AI collaboration brief

## 1. Project positioning

`fancy-skills` is a **small, Git-versioned library of Agent skills and Codex custom-agent definitions** (Markdown workflows, optional YAML bindings and references, plus standalone Agent TOML). It ships **no runtime server**, **no database**, and **no REST API**—value is in portable instructions consumed by Cursor, Claude Code, Codex-style hosts, or similar agent shells.

## 2. Core architecture

Three conceptual planes work together:

1. **Consumption plane** — Host products load `SKILL.md` and optional `skills/*/agents/*.yaml`; Codex loads registered top-level `agents/*.toml` roles.
2. **Package plane** — Each skill under `skills/<name>/` bundles manifest (`SKILL.md` frontmatter), optional UI hooks (`agents/`), and optional deep references (`references/`); top-level `agents/` stores reusable custom-agent definitions.
3. **Documentation plane** — Root `README.md` and `CLAUDE.md` explain repo-wide conventions so humans and AI share one map.

## 3. Key modules

| Path | Role |
|------|------|
| `skills/analyze-ai-agent-codebase/` | Methodology skill for reading AI agent codebases; primary artifact is `SKILL.md`, with deferred templates under `references/`. |
| `skills/bootstrap-ai-collab-infra/` | Meta-playbook skill that prescribes how to author `docs/*`, `CLAUDE.md`, and the read-only `docs-auto-sync` helper for other repositories. |
| `skills/feature-intake/` | Frontend-only intake skill that turns an HTML prototype + backend API doc pair into a Feature Intake Spec, with a built-in 5-class gap scanner. Ships its own spec template, checklist, and real-case references. |
| `skills/interview-prep-from-project/` | Mines an existing code project for resume highlights, interviewer-style questions, and reference answers, producing three Chinese Markdown documents. |
| `skills/jira-auto-fix/` | Codex-native JIRA bug workflow with stable reproduction, evidence-backed diagnosis, approval gates, multimodal attachment inspection, regression testing, and local-commit-only delivery. |
| `skills/jira-update/` | Guarded JIRA write workflow that converts a completed repair handoff into a comment, confirmed tester assignment, and explicit transition after a read-only preview. Ships a validated WARP default path (`Start Process` → `Start Review` → `Start Test` → `TEST`) and reporter-as-tester convention as confirmation-packet defaults, not as permission to write. |
| `skills/my-jira-query/` | Read-only JIRA query skill backed by a standard-library Python client and a Git-ignored, skill-local `.env` configuration. |
| `skills/propagate-api-contract-changes/` | Contract-propagation skill that traces backend API and Schema changes through frontend boundaries, consumers, fixtures, and verification. |
| `skills/run-local-fullstack-debug/` | Manual-only local environment and cross-layer debugging skill for startup, readiness, real end-to-end flows, and evidence-backed fault localization. |
| `skills/spec-to-executable-tickets/` | Manual-only specification convergence skill with Analysis and Delivery modes; turns multi-source product evidence into human-owned specs, evidence-backed gaps, and dependency-ready Tickets, including frontend interaction extraction and real Chrome acceptance. |
| `skills/write-weekly-report/` | Read-only git-log skill that groups recent commits by project theme into a Chinese weekly report with title/detail items; defaults to the `liushengpeng` / `shengpeng.liu` author identity and explicit date ranges. |
| `skills/*/agents/` | Thin YAML descriptors (`display_name`, `default_prompt`) for hosts that substitute `$<skill-name>` tokens. |
| `agents/ticket-queue-executor.toml` | Codex custom Agent that executes eligible repository Tickets serially in dependency order and records verification evidence. |
| `tests/` | Cross-skill Python unit tests (e.g. `test_jira_update.py` covering the `jira-update` script). |

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
5. To fix a JIRA bug, configure `skills/jira-auto-fix/.env` from `.env.example` and invoke **`jira-auto-fix`**; it must reproduce and obtain solution approval before editing, and it stops after a local commit. It can then hand the repair packet to **`jira-update`** in the same session.
6. To comment on and return a completed fix to testing, configure `skills/jira-update/.env`, invoke **`jira-update`**, inspect the live workflow, and explicitly confirm the exact comment, tester, and transition before writing. For standard WARP issues, the skill proposes the default path (`11 / Start Process` → hidden `Start Review` → hidden `Start Test` → final status `TEST`) and the reporter as tester; one confirmation of that packet authorizes the whole write.
7. To query JIRA without changing code, configure `skills/my-jira-query/.env` from `.env.example` and invoke **`my-jira-query`** with an issue key.
8. To install the custom Ticket executor, copy `agents/ticket-queue-executor.toml` into the Codex agents directory and register `[agents.ticket_queue_executor]` in the user configuration as shown in `README.md`.
9. To draft a weekly report, invoke **`write-weekly-report`** with an explicit or relative time range; it reads the local git log, groups commits into 5–8 project themes (default author `liushengpeng` / `shengpeng.liu`), and prints a Chinese ordered list with title/detail pairs.

There is **nothing to `npm install` or `docker compose up`** in this repository today.

## 6. Guardrails / forbidden zones

待开发人员补充

## 7. Historical baggage / known debt

待开发人员补充
