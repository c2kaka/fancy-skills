# fancy-skills

This repository stores reusable Agent skills, Codex custom-agent definitions, and lightweight documentation for collaborating with AI tools on this corpus.

## Quick Start

Install a skill with:

```bash
npx skills add c2kaka/fancy-skills --path skills/<skill-name>
```

Replace `<skill-name>` with a folder under `skills/`, for example `ai-agent-framework-design-guide`, `analyze-ai-agent-codebase`, `bootstrap-ai-collab-infra`, `change-risk-review`, `codex-local-saas-browser`, `feature-intake`, `interview-prep-from-project`, `jira-auto-fix`, `jira-report-quality-issue`, `jira-update`, `my-jira-query`, `propagate-api-contract-changes`, `run-local-fullstack-debug`, `spec-to-executable-tickets`, `verify-frontend-delivery`, `video-insight-report`, or `write-weekly-report`.

Then invoke in your agent terminal (or load the same skill name in your host's skill picker):

```
/ai-agent-framework-design-guide # Analyze an AI agent system and draft a Chinese-first framework design document
/analyze-ai-agent-codebase      # Methodically read an unfamiliar AI-agent codebase
/bootstrap-ai-collab-infra      # Scaffold layered docs, integration catalog, and CLAUDE.md for another repo
/change-risk-review             # Review git changes for risk classification before commit
/codex-local-saas-browser       # Prepare CogDB SaaS localhost:3000 for the Codex in-app browser
/feature-intake                 # Reverse a single source of truth from HTML prototype + backend API docs, surfacing implicit business behavior as explicit human decisions
/interview-prep-from-project    # Mine an existing project for resume highlights, interview questions, and reference answers as Markdown docs
/jira-auto-fix                  # Diagnose with a pyramid/Mermaid review, then test, fix, and locally commit after approvals
/jira-report-quality-issue      # Review coding work and file approved, verified JIRA issues with screenshot evidence
/jira-update                    # Preview and apply a completed WARP JIRA fix using the reporter as tester
/my-jira-query                  # Query and summarize a JIRA issue using skill-local .env credentials
/propagate-api-contract-changes # Carry backend contract changes through every affected frontend layer
/run-local-fullstack-debug      # Start, integrate, and trace failures across a local full-stack system
/spec-to-executable-tickets     # Convert product materials into human-owned specs, evidence-backed gaps, and dependency-ready tickets
/verify-frontend-delivery       # Explicitly prepare a frontend product contract or independently verify a frontend change
/video-insight-report           # Turn one public YouTube/Bilibili video into an evidence-linked offline HTML report
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
- `codex-local-saas-browser`: deterministically prepare and verify CogDB-backed `saas-frontend` HTTPS at `localhost:3000` for the Codex in-app browser, with pinned public certificate trust, exact OIDC callback checks, worktree ownership detection, and safe browser handoff
- `feature-intake`: reverse-engineer a Feature Intake Spec from an HTML prototype + backend API docs, scan for five classes of implicit-behavior gaps, and force every gap to an explicit human decision or TODO before implementation
- `interview-prep-from-project`: mine an existing code project for resume highlights, interview questions, and reference answers, producing three Chinese Markdown documents
- `jira-auto-fix`: stably reproduce and diagnose a JIRA bug, summarize the review top-down as a plain-language business example, root cause, and recommended solution with evidence-backed Mermaid diagrams when useful, require solution approval before edits, add a regression test, implement the fix, and stop after a locally approved commit
- `jira-report-quality-issue`: explicitly review the current coding delivery, prepare evidence-backed JIRA drafts and screenshot payloads, then create and verify self-assigned issues only after exact fingerprint approval; its skill-local `.env` accepts JSON-array defaults such as `JIRA_COMPONENTS=["Studio Coordinator"]` and `JIRA_FIX_VERSIONS=["TranswarpCloud Future"]`, while explicitly supplied draft fields (including empty arrays) take precedence
- `jira-update`: turn a completed repair handoff into a confirmed JIRA comment, tester assignment, and workflow transition, with read-only inspection, an approved WARP default path (`Start Process` → `Start Review` → `Start Test` → `TEST`), reporter-as-tester default, and explicit write approval
- `my-jira-query`: query JIRA issue details through a read-only Python client configured by a Git-ignored, skill-local `.env` file
- `propagate-api-contract-changes`: trace backend API and Schema changes through frontend clients, types, mappers, state, UI, fixtures, and tests, then verify the complete contract path
- `run-local-fullstack-debug`: manually start and verify a repository's local stack, exercise a real end-to-end flow, and localize failures across browser, frontend, gateway, backend, and data dependencies
- `spec-to-executable-tickets`: convert PRDs, prototypes, contracts, code, and runtime evidence into Delivery and Interaction Specs, human decision packets, proven implementation gaps, and executable Tickets; optionally hand approved Tickets to the dependency-aware executor for implementation and real Chrome acceptance
- `verify-frontend-delivery`: explicitly prepare and freeze a source-fingerprinted frontend product contract, or independently audit a frontend diff with risk-required gates, evidence levels, baseline deltas, and deterministic PASS/FAIL/BLOCKED reports
- `video-insight-report`: analyze one public YouTube or Bilibili video around the user's questions, use subtitles or explicitly prepared local MLX Whisper transcription, select timestamped real-frame evidence, and deterministically render an offline HTML report with a pyramid summary and first-principles critique
- `write-weekly-report`: generate a Chinese weekly report from recent git commits, grouped into 5–8 project themes with concise per-item details, defaulting to the `liushengpeng` / `shengpeng.liu` author identity

## Video Insight Report

Install this skill by itself with:

```bash
npx skills add c2kaka/fancy-skills --path skills/video-insight-report
```

Example prompt:

```text
Use $video-insight-report to analyze https://www.youtube.com/watch?v=VIDEO_ID.
I want to understand the author's core argument, the evidence behind it, and
whether the conclusion still holds when rebuilt from first principles.
```

The minimum input is one public YouTube/Bilibili URL plus the user's questions. The skill prefers non-empty platform subtitles, falls back to explicitly prepared local MLX Whisper transcription for captionless videos, extracts real frames at evidence timestamps, and writes `report.json` plus an offline `report.html`. A first local-ASR model download, cloud transcription, authentication, or clearly high resource use remains an explicit confirmation boundary. `COMPLETE`, `INCOMPLETE`, `BLOCKED`, and `FAILED` are distinct outcomes; missing real frames cannot be reported as success.

## Verify Frontend Delivery

Install this skill by itself with:

```bash
npx skills add c2kaka/fancy-skills --path skills/verify-frontend-delivery
```

It is explicit-only: ordinary frontend implementation or review requests do not trigger it.

| Mode | Use it for | Completion boundary |
|---|---|---|
| `prepare` | Fingerprint PRDs, prototypes, contracts, repository identity, and the target diff; build the product contract and risk-required gates | Stop after the user approves a separately frozen contract; never start implementation |
| `verify` | Audit a frozen contract with an independent fresh context and evidence-ranked regression gates | Generate deterministic `gate-report.json` and `gate-report.md`; never fix, commit, push, update JIRA, or approve waivers |
| `status` | Read an existing report without rerunning gates | Return current blockers, source drift, evidence levels, and reusable checkpoints |

Example prompts:

```text
Use $verify-frontend-delivery in prepare mode for this frontend change. The PRD is
<prd-path>, the prototype is <prototype-path>, and the explicit base is <git-ref>.

Use $verify-frontend-delivery in verify mode with frozen contract <contract-path>
and change <base>..<head>. Preserve the product repository and write only local
run artifacts outside it.

Use $verify-frontend-delivery in status mode for <gate-report.json>.
```

The default local run root is `~/.local/state/verify-frontend-delivery/runs`. The JSON report is authoritative; its Markdown companion is generated from the same data. Fixture, synthetic UI, real backend, and real-page E2E evidence are distinct and cannot substitute for one another. The first rollout is local-only: the skill does not update CI or delete run artifacts automatically.

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
