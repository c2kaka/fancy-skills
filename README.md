# fancy-skills

This repository stores reusable Agent skills, Codex custom-agent definitions, and lightweight documentation for collaborating with AI tools on this corpus.

## Quick Start

Install a skill with:

```bash
npx skills add c2kaka/fancy-skills --path skills/<skill-name>
```

Replace `<skill-name>` with a folder under `skills/`, for example `ai-agent-framework-design-guide`, `analyze-ai-agent-codebase`, `bootstrap-ai-collab-infra`, `change-risk-review`, `feature-intake`, `interview-prep-from-project`, `jira-auto-fix`, `jira-report-quality-issue`, `jira-update`, `my-jira-query`, `propagate-api-contract-changes`, `run-local-fullstack-debug`, `spec-to-executable-tickets`, or `write-weekly-report`.

Then invoke in your agent terminal (or load the same skill name in your host's skill picker):

```
/ai-agent-framework-design-guide # Analyze an AI agent system and draft a Chinese-first framework design document
/analyze-ai-agent-codebase      # Methodically read an unfamiliar AI-agent codebase
/bootstrap-ai-collab-infra      # Scaffold layered docs, integration catalog, and CLAUDE.md for another repo
/change-risk-review             # Review git changes for risk classification before commit
/feature-intake                 # Reverse a single source of truth from HTML prototype + backend API docs, surfacing implicit business behavior as explicit human decisions
/interview-prep-from-project    # Mine an existing project for resume highlights, interview questions, and reference answers as Markdown docs
/jira-auto-fix                  # Diagnose with a pyramid/Mermaid review, then test, fix, and locally commit after approvals
/jira-report-quality-issue      # Review coding work and file approved, verified JIRA issues with screenshot evidence
/jira-update                    # Preview and apply a completed WARP JIRA fix using the reporter as tester
/my-jira-query                  # Query and summarize a JIRA issue using skill-local .env credentials
/propagate-api-contract-changes # Carry backend contract changes through every affected frontend layer
/run-local-fullstack-debug      # Start, integrate, and trace failures across a local full-stack system
/spec-to-executable-tickets     # Convert product materials into human-owned specs, evidence-backed gaps, and dependency-ready tickets
/write-weekly-report            # Generate a Chinese weekly report grouped by project themes from recent git commits
```

Your host may use `@` mentions, rules, or file paths instead of slash commands; the skill identity is the folder name under `skills/`.

## Structure

- `skills/`: each skill lives in its own folder
- `skills/<skill-name>/SKILL.md`: trigger metadata and workflow
- `skills/<skill-name>/agents/`: UI-facing agent metadata (optional)
- `skills/<skill-name>/references/`: load-on-demand reference material (optional)
- `agents/`: reusable Codex custom-agent TOML definitions
- `tests/`: cross-skill Python tests (e.g. `test_jira_update.py`)

## Included Skills

- `ai-agent-framework-design-guide`: analyze existing AI agent / skill / runtime systems and write Chinese-first framework design documents with rollout phases, plus optional risks and open questions
- `analyze-ai-agent-codebase`: analyze open-source AI agent repositories through layers, contracts, execution loops, tools, and trade-offs
- `bootstrap-ai-collab-infra`: generate the layered-docs + API catalog + conceptual schema + `CLAUDE.md` + read-only `docs-auto-sync` playbook for arbitrary repositories
- `change-risk-review`: review git changes for behavior, protocol, and architecture risk before commit, then generate a classified commit message after user confirmation
- `feature-intake`: reverse-engineer a Feature Intake Spec from an HTML prototype + backend API docs, scan for five classes of implicit-behavior gaps, and force every gap to an explicit human decision or TODO before implementation
- `interview-prep-from-project`: mine an existing code project for resume highlights, interview questions, and reference answers, producing three Chinese Markdown documents
- `jira-auto-fix`: stably reproduce and diagnose a JIRA bug, summarize the review top-down as a plain-language business example, root cause, and recommended solution with evidence-backed Mermaid diagrams when useful, require solution approval before edits, add a regression test, implement the fix, and stop after a locally approved commit
- `jira-report-quality-issue`: explicitly review the current coding delivery, prepare evidence-backed JIRA drafts and screenshot payloads, then create and verify self-assigned issues only after exact fingerprint approval; its skill-local `.env` accepts JSON-array defaults such as `JIRA_COMPONENTS=["Studio Coordinator"]` and `JIRA_FIX_VERSIONS=["TranswarpCloud Future"]`, while explicitly supplied draft fields (including empty arrays) take precedence
- `jira-update`: turn a completed repair handoff into a confirmed JIRA comment, tester assignment, and workflow transition, with read-only inspection, an approved WARP default path (`Start Process` → `Start Review` → `Start Test` → `TEST`), reporter-as-tester default, and explicit write approval
- `my-jira-query`: query JIRA issue details through a read-only Python client configured by a Git-ignored, skill-local `.env` file
- `propagate-api-contract-changes`: trace backend API and Schema changes through frontend clients, types, mappers, state, UI, fixtures, and tests, then verify the complete contract path
- `run-local-fullstack-debug`: manually start and verify a repository's local stack, exercise a real end-to-end flow, and localize failures across browser, frontend, gateway, backend, and data dependencies
- `spec-to-executable-tickets`: convert PRDs, prototypes, contracts, code, and runtime evidence into Delivery and Interaction Specs, human decision packets, proven implementation gaps, and executable Tickets; optionally hand approved Tickets to the dependency-aware executor for implementation and real Chrome acceptance
- `write-weekly-report`: generate a Chinese weekly report from recent git commits, grouped into 5–8 project themes with concise per-item details, defaulting to the `liushengpeng` / `shengpeng.liu` author identity

## Included Agents

- `ticket-queue-executor`: continuously execute eligible repository Tickets one at a time in dependency order, verify each Ticket, record evidence, and rescan until no executable work remains

Install and register the Agent in Codex:

```bash
mkdir -p ~/.codex/agents
cp agents/ticket-queue-executor.toml ~/.codex/agents/
```

```toml
[agents.ticket_queue_executor]
description = "Execute repository Ticket queues sequentially according to dependency and status constraints, verify each Ticket, update evidence and status, then rescan until no executable work remains."
config_file = "agents/ticket-queue-executor.toml"
nickname_candidates = ["Queue Runner", "Ticket Executor", "Dependency Walker"]
```

## Companion files

- [`CLAUDE.md`](CLAUDE.md): concise onboarding for AI assistants working in this repo
