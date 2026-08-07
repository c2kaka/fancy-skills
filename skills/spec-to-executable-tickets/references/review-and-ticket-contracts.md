# Review and Ticket Contracts

Use these contracts to lower human review cost and prevent uncertainty from leaking into implementation Tickets.

## Decision Packet

Create one packet per mutually exclusive product decision:

```text
Decision ID and title
Decision owner and required co-owner
Question that must be answered
Why the decision is required now
Source statements or contradiction
Affected REQ/RULE/STATE/SCN and downstream Ticket count
Risk, reversibility, and latest useful decision time
Two or three mutually exclusive options
User, data, contract, engineering, and migration impact per option
Recommended option and rationale
Concrete examples that distinguish the options
Result of no decision: blocked branch or authorized default policy
Final choice, conditions, owner, timestamp, and provenance
```

Do not ask broad questions that transfer analysis back to the Product Decision Owner. Rank packets by core-model impact, downstream unlock count, risk, irreversibility, shared-contract reach, and urgency. Present the smallest batch that unlocks the most independent work, normally five to seven or fewer.

## Product review bundle

Generate a compact review view from the canonical model:

- capability maturity and current Gate;
- semantic changes since the last review;
- unresolved Decision Packets and recommendations;
- affected users and scenarios;
- prototype versus PRD contradictions;
- critical interaction-state coverage;
- ready and blocked delivery slices;
- implementation evidence or Product Outcome scenarios when applicable.

Do not make the product reviewer browse the full engineering Gap Analysis. Persist every answer into the Decision Ledger; chat history is not the source of truth.

## Gap record

Require:

```text
Gap ID
Linked REQ/RULE/STATE/SCN/DEC
Expected observable behavior
Current observed behavior
Evidence source and exact location or command
First point of divergence
Affected UI/API/data/worker/external layers
Risk and reversibility
Confidence: proven | strong inference | investigation required
Classification
Recommended treatment
Verification method
Downstream Ticket links
```

Create an implementation Ticket only when expected behavior is settled and current evidence proves a difference.

## Executable Ticket contract

Require every Ticket to contain:

```text
Ticket ID and repository-native status
One verifiable outcome
Linked REQ/RULE/STATE/SCN/DEC/GAP IDs
Current implementation evidence
Exact difference to close
Scope and explicit non-goals
Affected boundaries and allowed change surface
Blocking dependencies
Inputs, outputs, side effects, and invariants
Implementation constraints without prescribing unnecessary mechanics
Executable acceptance scenarios
Compatibility and migration requirements
Focused and end-to-end verification methods
Known risks and evidence limitations
Completion evidence requirements
```

Prefer a vertical user-observable slice. Separate a shared contract, migration, or infrastructure Ticket only when it has an independently verifiable outcome and is a real prerequisite.

## Ticket admission checklist

Set the repository-equivalent of `ready-for-agent` only when all answers are yes:

- Is the desired product behavior confirmed?
- Are high-impact semantic decisions resolved or outside this branch?
- Is the current implementation gap proven?
- Is the outcome bounded and independently verifiable?
- Are scope and non-goals explicit?
- Are dependencies present and correctly ordered?
- Are inputs, outputs, invariants, and side effects clear?
- Are acceptance scenarios executable rather than subjective?
- Does verification include real integration where the behavior requires it?
- Can an implementation Agent complete the Ticket without inventing product semantics?

If the last answer is no, route the missing information to a Decision Packet, domain investigation, interaction-design task, technical Spike, or implementation investigation instead of marking the Ticket ready.

## Completion evidence

Require exact commands or actions, observed results, acceptance-item mapping, runtime or browser evidence, and disclosed limitations. Keep these claims distinct:

- static code appears consistent;
- focused tests pass;
- process is running;
- service is ready;
- direct API flow succeeds;
- frontend and backend are integrated;
- UI matches interaction and visual requirements;
- Product Decision Owner accepted the outcome.

Never collapse a lower claim into a higher one.
