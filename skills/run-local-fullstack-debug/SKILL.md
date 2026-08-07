---
name: run-local-fullstack-debug
description: Start and verify a repository's local frontend, backend, infrastructure, and dependent services; exercise a real end-to-end flow; and localize failures across browser, frontend, proxy or gateway, API, worker, database, cache, queue, and external-service boundaries. Use only when the user explicitly invokes `$run-local-fullstack-debug`; never select this skill implicitly.
---

# Run Local Full-Stack Debug

Bring up the repository's real local stack, prove readiness at each boundary, reproduce one concrete flow, and produce an evidence-backed fault location. Diagnose by default; modify application code only when the user also asks for a fix.

## 1. Establish scope and preserve state

1. Read every applicable `AGENTS.md`, the repository startup documentation, environment examples, manifests, task runners, container definitions, and the user's target scenario.
2. Inspect the worktree and preserve unrelated or uncommitted changes. Do not reset, clean, overwrite local configuration, or regenerate lockfiles without a demonstrated need.
3. Record which processes, containers, ports, and data services are already running. Treat them as user-owned; never stop or replace them merely because they conflict.
4. State the intended end state: which services must run, which user flow will be exercised, and whether this task is diagnosis-only or also authorizes a fix.
5. Never print secrets. Report missing variable names and their source, not secret values.

## 2. Reconstruct the real local topology

Build a compact runtime map from repository evidence, not assumptions:

```text
browser/client -> frontend dev server -> proxy/BFF/gateway -> API -> database/cache/queue
                                                      \-> worker / external dependency
```

For each relevant component, identify:

- its repository-provided start command and working directory;
- runtime and dependency prerequisites;
- configuration source, public URL, bind address, and port;
- upstream and downstream endpoints;
- health or readiness signal;
- logs and request-correlation mechanism;
- data initialization or migration requirement.

Prefer the repository's documented orchestration command. Do not invent a parallel startup system. If documentation and executable configuration disagree, treat executable configuration as evidence and report the drift.

## 3. Run preflight checks

Verify before starting anything:

- required runtimes and package-manager versions;
- installed dependencies using lockfile-preserving modes where available;
- required environment variable names and local configuration files;
- Docker or other infrastructure availability;
- port ownership and hostname resolution;
- database schema or migration status;
- required credentials, fixtures, or reachable external dependencies.

Do not run destructive database resets, broad cleanup, production commands, or data-replacing seeds without explicit authorization. If dependency installation is necessary, use the repository's pinned tool and preserve its lockfile unless the task requires changing dependencies.

## 4. Start in dependency order

Start only the missing components, from the bottom of the dependency graph upward:

1. database, cache, queue, object store, and local emulators;
2. migrations or safe initialization explicitly required by the repository;
3. API, gateway/BFF, and workers;
4. frontend dev server.

Use managed long-running command sessions when available so output remains observable. Capture the command, session identifier, component, and log location. If a process exits, inspect its first actionable error before restarting; do not enter a blind restart loop.

For every component, distinguish:

- **process started**: the process exists;
- **ready**: its documented health check passes;
- **integrated**: a real upstream caller successfully exercises it.

Do not infer readiness from an open port alone.

## 5. Exercise one real end-to-end flow

Translate the reported problem into a precise scenario with prerequisites, action, and expected observable result.

1. Probe the lowest useful API boundary directly with the repository's normal authentication and payload.
2. Exercise the same flow through the actual frontend when UI is involved. Prefer the `chrome:control-chrome` skill and the user's existing Chrome session for real-page inspection.
3. Capture the browser console and network request, the proxy or gateway forwarding behavior, backend request logs, worker events, and resulting data-layer state as applicable.
4. Carry a real request ID, trace ID, entity ID, timestamp window, or other stable correlation key across layers. If none exists, correlate by a narrow timestamp and exact input while stating the limitation.
5. Verify both the response and the intended side effect. A `2xx` response alone does not prove persistence, job completion, cache invalidation, or correct UI rendering.

Never describe mocks, fixtures, bypassed authentication, stubbed dependencies, or synthetic responses as successful real integration.

## 6. Localize failures across boundaries

Trace the first point where observed behavior diverges from the expected contract. Check boundaries in causal order:

1. browser state, console, request construction, and runtime configuration;
2. frontend proxy, CORS, cookies, authentication, and base URL;
3. gateway/BFF route, method, headers, body transformation, and upstream selection;
4. backend routing, validation, authorization, business logic, and exception path;
5. database query, transaction, migration, constraints, and persisted state;
6. cache, queue, worker, event delivery, and eventual-consistency timing;
7. external dependency connectivity, credentials, contract, and rate limits.

At each boundary compare what was sent, what was received, and what the next layer expected. Separate:

- root cause from downstream symptoms;
- application defects from environment or data defects;
- startup failures from readiness failures;
- contract mismatches from connectivity failures;
- reproducible evidence from hypotheses.

Change one meaningful variable at a time and rerun the smallest reproducer. Do not patch multiple layers merely to make the symptom disappear. If the user requested diagnosis only, stop after locating the fault and recommend a bounded fix without editing code.

## 7. Verify recovery or report the blocker

If a fix is authorized and implemented, rerun in increasing scope:

1. focused unit or contract check;
2. direct API reproducer;
3. complete local end-to-end flow;
4. relevant lint, typecheck, tests, or build.

If blocked, provide the exact failing command or request, relevant sanitized output, affected boundary, attempted checks, and the missing external input. Do not claim the stack is healthy when a required layer remains unverified.

## 8. Leave an auditable handoff

Report:

- components started, reused, failed, or intentionally skipped;
- URLs, ports, health checks, and managed session identifiers;
- the exact end-to-end scenario and observed result;
- the cross-layer evidence chain and first failing boundary;
- root cause with confidence, or ranked hypotheses with disambiguating checks;
- files changed, validations run, and remaining limitations;
- which services remain running and how to stop only those started by this task.

Honor the user's requested final state. If the purpose was to leave a development environment running, keep successfully started services available and report how they are managed. Otherwise stop only the processes or containers started by this task; never tear down pre-existing services.
