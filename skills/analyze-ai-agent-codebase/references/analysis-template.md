# AI Agent Codebase Analysis Template

Use this template when the user wants a structured report instead of an informal walkthrough.

## 1. System Classification

- Primary identity:
- Secondary identities:
- Main product surfaces:
- Best comparison point:

## 2. Layer Map

- Layer 1:
- Layer 2:
- Layer 3:
- Layer 4:
- Dependency direction:
- Narrow waist:

## 3. High-Signal Files

- File:
  Why it matters:
- File:
  Why it matters:
- File:
  Why it matters:

Prefer contracts, registries, loops, and one representative tool or adapter.

## 4. Core Contracts

- Shared message or event types:
- Model or provider contract:
- Tool contract:
- Extension or plugin contract:
- Config or prompt contract:

## 5. Critical Execution Paths

### Request path

- entry
- context assembly
- dispatch
- streaming or result handling
- state update

### Tool path

- tool declaration
- selection
- validation
- execution
- result reinjection

## 6. Control Surfaces

- Capability control:
- Permission control:
- Context control:
- Memory or compaction control:

## 7. Built-In vs Composed Features

- Feature:
  Built-in or composed:
  Underlying primitive:
- Feature:
  Built-in or composed:
  Underlying primitive:

## 8. Trade-Offs

For each major subsystem, use:

- got:
- gave up:
- worth it because:

## 9. Influence Radius and Cross-Cutting Risk Map

For the feature or subsystem under study:

- layers touched:
- modules that share the same state:
- implicit dependencies (config flags, queues, schedules, caches):
- same concept implemented differently across modules:
- risk classification per crossing point (same-layer / cross-layer / cross-module / cross-state):

## 10. Constraints and Decision History

- explicit constraints obeyed:
- implicit conventions discovered (not enforced by types or tests):
- constraint violations or boundary crossings found:
- design decisions traced via git history (blame, PRs, commit messages):
- intentionally inelegant code and the constraints that caused it:

## 11. Explanation-Power Self-Check

- why was it done this way? (intent, not mechanism):
- what alternatives were considered or would be viable?:
- where is the weakest point or highest risk?:

If any answer is missing or shallow, revisit the relevant contracts and history before finalizing the report.

## 12. Extension Paths

- safest customization path:
- moderate customization path:
- high-risk architectural surgery:
- files to start from:

## 13. Applicability Judgment

- best-fit use cases:
- poor-fit use cases:
- likely scaling constraints:
- what a new contributor should read first:
