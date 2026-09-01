# Review Output Contract

Use this structure for a full design-and-code review. Scale it down for narrow requests, but preserve evidence, severity, and uncertainty discipline.

## 1. Findings first

List confirmed findings in descending severity. If there are no actionable findings, say so explicitly and identify any residual evidence gaps.

Use these severity levels:

| Severity | Meaning |
|---|---|
| `Critical` | Violates a core invariant or creates credible security, integrity, permission, irreversible compatibility, or systemic correctness risk. Blocks approval. |
| `High` | Design and implementation materially contradict each other, or a boundary/ownership decision causes wide propagation or likely redesign. |
| `Medium` | Localized information leakage, cognitive load, error semantics, or verification weakness that can be repaired within the current design. |
| `Low` | Non-blocking weakness in clarity, maintainability, or documented intent with a concrete future cost. |

Do not assign a severity to an unsupported suspicion. Put it under `Open questions` with the evidence needed to resolve it.

Each finding must follow this schema:

```markdown
### High — <specific design failure>

**Claim:** <one falsifiable sentence>

**Evidence:**
- `<path:line or document section>` — <what it establishes>
- `<test or command>` — <what it does or does not verify>

**Mechanism:** <how knowledge, state, dependency, or error crosses the wrong boundary>

**Impact:** <affected behavior, future change, or failure scenario>

**Correction direction:** <the smallest coherent design correction; avoid coding the fix unless asked>

**Verification:** <test, trace, experiment, or review evidence that would close the finding>
```

Keep file ranges tight. Quote only the minimum text needed to establish the finding.

## 2. Verdict

Choose exactly one:

- `Approve`: no material design defect found and evidence is proportionate to the claims.
- `Approve with changes`: the design is coherent, but one or more bounded corrections are required before completion.
- `Request redesign`: a high-impact boundary, ownership, contract, or error-model decision is unsound; local patching would preserve the underlying complexity.
- `Insufficient evidence`: the available artifacts do not support a responsible design or implementation verdict.

The verdict summarizes the findings; it must not introduce new criticism.

Add confidence as `high`, `medium`, or `low`, based on source completeness and verification strength. Confidence is not severity.

## 3. Review basis

State:

- artifacts reviewed
- repository or revision scope
- artifacts requested but unavailable
- commands or tests inspected or run
- whether runtime behavior was directly observed

Distinguish source inspection, static checks, unit tests, integration tests, mocked behavior, and real-system evidence. Do not promote one evidence level to another.

## 4. Reconstructed design contract

Summarize:

- problem and intended outcome
- constraints
- invariants
- non-goals
- key assumptions
- failure and compatibility boundaries

Label reviewer-inferred items. If the coding agent did not record an important decision, say so.

## 5. Design-to-code traceability

Use a table:

| Design claim | Implementation evidence | Verification evidence | Status |
|---|---|---|---|
| <claim> | `<path:line>` | `<test/command>` or none | Implemented / Partial / Contradicted / Unverified |

Include all material design claims, not every implementation detail. Add code behavior absent from the design as a separate row prefixed `Undeclared behavior:`.

## 6. Complexity analysis

Report only relevant dimensions:

| Dimension | Evidence-based judgment |
|---|---|
| Change amplification | <where one change propagates and why> |
| Cognitive load | <what callers or maintainers must know> |
| Unknown unknowns | <hidden dependencies or unclear ownership> |
| Module depth | <capability delivered relative to interface cost> |
| Information leakage | <knowledge duplicated across boundaries> |
| Error semantics | <who detects, recovers, observes, and acts> |
| Generality | <stable concept or speculative abstraction> |

Do not calculate a total complexity score. Prefer causal explanations and concrete future-change examples.

## 7. Alternative design

Include this section when a material decision is difficult to reverse or when a `High`/`Critical` finding challenges the current boundary.

Compare at least two genuinely different options:

| Criterion | Current design | Alternative |
|---|---|---|
| State owner | | |
| Interface and dependency cost | | |
| Failure and recovery | | |
| Compatibility/migration | | |
| Reversibility | | |

Recommend an option only after evaluating both against the reconstructed constraints. An alternative is not automatically better because it is different.

## 8. Verification gaps

List claims whose evidence is weaker than their wording. For each gap, specify the smallest proportionate evidence needed, such as:

- a contract or counterexample test
- a cross-component integration scenario
- a concurrency or retry test
- a migration dry run
- a runtime trace or observable metric
- a real-page or real-backend check
- confirmation from the authoritative business or protocol owner

## 9. Open questions and assumptions

Keep unresolved matters separate from findings. State:

- why the answer matters
- what source or experiment can resolve it
- whether it blocks the verdict

## 10. Recommended order

End with the smallest coherent sequence:

1. correct invariant, ownership, or contract failures
2. align design and implementation
3. close risk-proportionate verification gaps
4. improve non-blocking clarity

Do not turn this into an implementation plan unless the user asks for one.

## Compact example

```markdown
### High — Cache invalidation ownership leaks to callers

**Claim:** The implementation contradicts the document's claim that `ProfileStore` owns cache consistency because three services construct cache keys and invalidate entries independently.

**Evidence:**
- `design/profile-store.md`, "Ownership" — assigns cache consistency to `ProfileStore`.
- `src/user-service.ts:84` — constructs and invalidates the profile key.
- `src/import-service.ts:126` — repeats the rule with different ordering.

**Mechanism:** Cache representation and sequencing knowledge is duplicated across callers, increasing change amplification and creating an undocumented ordering dependency.

**Impact:** A new write path can return stale data even while focused service tests pass.

**Correction direction:** Move invalidation policy behind the state-owning module and expose an operation that completes the caller's business intent.

**Verification:** Add contract tests across both write paths, including retry and concurrent-read scenarios.
```
