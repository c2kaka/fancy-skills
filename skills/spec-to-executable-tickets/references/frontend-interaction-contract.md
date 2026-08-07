# Frontend Interaction Contract

Use this reference whenever source materials include an HTML prototype, screenshots, interactive mockup, or an existing frontend flow.

## Prototype authority

Treat explicitly visible information hierarchy, visual structure, operation entry points, and demonstrable transitions as implementation baselines. Treat sample data as examples rather than a domain schema. Treat missing states as undefined. Escalate PRD conflicts, internal inconsistency, and behavior affecting permissions, money, persistent data, or irreversible actions.

Restore user-observable results, not prototype-generator internals. Do not mechanically copy generated DOM hierarchies, inline CSS, absolute positioning, hard-coded data, fake delays, or demo-only shortcuts. Reuse the repository's architecture and design system when doing so preserves the specified outcome.

## Observe before extracting

Run the prototype and exercise it in a real browser when possible. Prefer `chrome:control-chrome`, especially when the target application depends on existing Chrome authentication or state.

For each route or view, inspect:

- entry conditions and navigation;
- information hierarchy and visual anchors;
- controls, menus, dialogs, drawers, tables, and forms;
- user actions and resulting state transitions;
- loading, success, failure, cancellation, and recovery behavior;
- visible and hidden permissions;
- responsive changes and overflow;
- keyboard, focus, and accessibility behavior shown or implied by existing project standards;
- network and persistent side effects when the prototype is connected.

Do not infer that a click is inert from source code alone when executable behavior can be observed.

## Interaction point model

Define each user capability as:

```text
Actor
Precondition
Entry surface
User action
Input and validation
State transition
Observable result
API/event/data side effect
Failure behavior
Recovery or cancellation behavior
Visual anchors
Responsive and accessibility constraints
```

Link each interaction point to stable `REQ-*`, `STATE-*`, `SCN-*`, and applicable `DEC-*` IDs.

## State coverage matrix

Generate relevant combinations across:

```text
view × role × domain state × data state × request state × failure type × viewport
```

At minimum consider initial loading, refresh, empty, populated, partial data, large data, validation error, network error, timeout, retry, duplicate submission, stale state, concurrent change, read-only, no permission, success, partial success, cancellation, and destructive confirmation when applicable.

Apply existing project conventions automatically only to low-risk reversible engineering states such as standard loading indicators, ordinary network retry, form validation presentation, focus behavior, and established responsive patterns.

Create Decision Packets for partial success policy, permission visibility, conflict resolution, retry with non-idempotent effects, destructive confirmation, rollback, or any missing state that changes the business result.

## Frontend Ticket slicing

Prefer scenario slices over component or layer slices. A Ticket should deliver one end-to-end interaction with real data boundaries and failure behavior. Treat components as implementation details unless a reusable design-system component is itself the independently verifiable prerequisite.

Avoid Tickets named only after a table, modal, component, API call, or styling task when those pieces cannot prove a user result independently.

## Chrome acceptance

Use three evidence layers:

1. **Visual**: compare prototype and application at relevant viewports; inspect layout, hierarchy, typography, spacing, color, overflow, responsive changes, and selected visual anchors.
2. **Interaction**: execute linked scenarios; verify mouse, keyboard, focus, menus, dialogs, validation, cancellation, feedback, failure, and recovery.
3. **Runtime integration**: inspect console and network behavior, use real authentication and API data, verify persistence and side effects, and confirm the result survives refresh when required.

Do not require whole-page pixel identity as the sole acceptance criterion. Browser, font, and real-data differences may be legitimate. Define critical visual anchors and scenario outcomes explicitly.

Do not call a UI Ticket complete from screenshots alone, a static prototype, mocked network responses, or a frontend-only happy path when the specification requires real backend behavior.
