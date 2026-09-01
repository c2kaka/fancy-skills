# Design Review Model

Use this reference to reason about why a design is simple or complex. It distills the complexity-centered philosophy associated with John Ousterhout's *A Philosophy of Software Design* and the evidence-linked analysis of his AI-era software-design interview. These are decision tools, not style commandments.

## 1. Start from the actual constraint

Software must remain understandable, modifiable, and verifiable while requirements, states, failures, and contributors grow. Human attention, working memory, and coordination bandwidth are limited. Every public interface, dependency, failure state, and ownership boundary consumes some of that budget.

AI can reduce the cost of producing code without reducing the cost of selecting boundaries, preserving constraints, coordinating changes, or validating behavior. More generated code can therefore increase complexity faster unless design and verification improve with it.

Distinguish:

- **Intrinsic complexity**: required by the problem domain; localize and expose it through coherent semantics.
- **Accidental complexity**: created by the chosen design; remove it before trying to hide it.

An abstraction does not make complexity disappear. It concentrates knowledge behind an owner and a contract. This only creates net value when the contract is stable and semantically complete, and when hidden operational costs remain observable.

## 2. Diagnose the three symptoms

### Change amplification

A conceptually small change requires edits in many places.

Ask:

- Where is the same decision or knowledge duplicated?
- Which modules must change together?
- Does a caller need to coordinate several low-level operations to express one business action?
- Will adding a new variant require modifying many existing branches?

### Cognitive load

A contributor must hold too many concepts, states, exceptions, or dependencies in mind at once.

Ask:

- What must a caller know that is not part of its own responsibility?
- How many abstractions must be traversed to understand one behavior?
- Are names and types carrying stable semantics, or must readers inspect implementations and call sites?
- Do wrapper layers add navigation without hiding decisions?

### Unknown unknowns

It is unclear which code or contract must change, or hidden dependencies are discovered only after failure.

Ask:

- Are dependencies and ownership explicit?
- Does the same concept have different names or meanings across layers?
- Are lifecycle, compatibility, fallback, and error rules documented and enforced?
- Can a reviewer identify all consumers of a changed contract?

Do not stop at naming a symptom. Trace the underlying knowledge, boundary, or state ownership that produces it.

## 3. Test module depth

A deep module offers substantial coherent capability through a comparatively simple interface. Depth is leverage, not size.

Evaluate:

- Does the interface express complete caller intent, or expose an internal procedure?
- Does the module own the state, policy, and failure semantics needed to fulfill that intent?
- Is the interface smaller and more stable than the implementation it hides?
- Can callers use it correctly without learning internal sequencing or representation?
- Does combining responsibilities improve information hiding, or merely form an incoherent large module?

Warning signs of a shallow module:

- one wrapper per implementation operation
- passthrough methods that add names but no semantic boundary
- callers repeat the same orchestration or error handling
- configuration exposes internal strategy unnecessarily
- a microservice boundary splits strongly coupled state while requiring synchronous coordination

Boundary reduction is not automatically good. Independent scaling, fault isolation, security domains, data ownership, deployment cadence, and team ownership may justify a smaller module. Compare those benefits against the extra interface and coordination surface.

## 4. Look for information leakage

Information leakage exists when one design decision is reflected in multiple modules or callers.

Common forms:

- duplicated key construction, validation, ordering, retry, or state-transition rules
- transport or persistence details leaking into domain code
- one schema interpreted differently by producers and consumers
- several components knowing which operations must occur together
- tests encoding implementation structure instead of public behavior

The remedy is not always another abstraction. First decide which owner should possess the knowledge. Then move the behavior and contract together so the knowledge has one authoritative home.

## 5. Evaluate generality without speculation

General-purpose modules can be deeper because their interfaces model stable concepts rather than one caller's current special case. But speculative frameworks add concepts before evidence exists.

Ask:

- Which requirement is fundamental, and which detail belongs only to today's caller?
- Can special cases be represented through a coherent general semantic model?
- Does generalization remove branches and duplicated knowledge, or just move them into configuration?
- Is the new extension point supported by real variation, or imagined future use?

Prefer the smallest general concept that explains existing variation and preserves likely change boundaries.

## 6. Decide what matters

Good design separates decisions that affect correctness, compatibility, ownership, and evolution from incidental implementation detail.

Require precision for:

- externally visible contracts and semantic meanings
- state ownership and lifecycle
- invariants and security boundaries
- idempotency, concurrency, failure, and recovery
- compatibility and migration exit conditions
- observability needed to operate hidden complexity

Allow implementation freedom where choices are cheap and reversible. A design document that specifies every helper while leaving ownership and error semantics vague has focused on the wrong things.

## 7. Design it twice, proportionately

Comparing alternatives breaks anchoring on the first plausible implementation. Apply it when a decision crosses public, data, security, deployment, or long-lived ownership boundaries.

Alternatives must differ in a material dimension such as:

- state owner
- dependency direction
- contract semantics
- consistency model
- execution boundary
- migration strategy

Compare them against the same constraints:

- simplicity for callers
- change propagation
- failure containment and recovery
- operability and security
- migration cost
- reversibility

For uncertain but cheap choices, a small implementation experiment may produce better information than extended speculation.

## 8. Define errors out without hiding failures

Each externally visible error adds a state callers must understand. Reduce unnecessary errors by changing semantics, not by swallowing them.

Review:

- Can several internal causes share one caller-actionable outcome?
- Can an idempotent or declarative operation remove an invalid sequencing state?
- Does the owner recover locally when callers cannot act meaningfully?
- Are genuine infrastructure, permission, integrity, and security failures detected and observable?
- Does fallback preserve invariants, or return plausible but false success?

An error has been designed out only when the exceptional state is no longer necessary. An ignored error still exists and is now harder to diagnose.

## 9. Treat comments and tests as abstraction evidence

Useful interface documentation records what code alone cannot reliably communicate:

- intent and invariants
- preconditions and postconditions
- units and limits
- concurrency and ordering
- lifecycle and ownership
- error and compatibility semantics

Tests should demonstrate contracts, counterexamples, and system interactions proportionate to the risk. They must not become the sole generator of design through one local example at a time. Periodically step back and ask whether the test suite describes a coherent abstraction or a collection of patched cases.

## 10. Review the feedback loop

Design continues through implementation, testing, operations, and review. Unknown domains require feedback and revision.

Look for:

- assumptions that can be tested early
- instrumentation that can reveal hidden cost or failure
- safe rollout and rollback boundaries
- review by people or agents with independent context
- an explicit point where evidence can revise the design

Do not interpret iteration as permission to omit high-cost invariants or irreversible contract decisions. Match the amount of up-front comparison to decision cost and reversibility.

## 11. Coding-agent-specific reasoning checks

Coding agents make implementation cheap and can produce locally convincing artifacts quickly. Reviewers should therefore distinguish fluent completion from grounded design.

For every important claim, ask:

1. What source establishes this semantic fact?
2. Which code path implements it?
3. Which evidence verifies the relevant failure or counterexample?
4. What assumption remains if any link is missing?

Reject semantic shortcuts such as keyword routing, enumerated patches, or regex recovery when the task requires intent, protocol, or domain understanding. A deterministic rule is appropriate only when the domain itself supplies a deterministic grammar or closed set.

Also test whether the agent followed a local call chain beyond the approved scope, duplicated an existing mechanism it failed to discover, or declared success using evidence weaker than the claim.

## Provenance and limits

The model is informed by:

- John Ousterhout, *A Philosophy of Software Design*, Second Edition
- the author's public second-edition summary: <https://web.stanford.edu/~ouster/cgi-bin/book.php>
- the evidence-linked report for the interview "AI时代的软件设计哲学"

The interview provides mechanism arguments, professional cases, and teaching observations rather than controlled experimental proof. Treat predictions about AI, and broad criticisms of TDD, short methods, or microservices, as conditional claims. Judge concrete outcomes in the target system.
