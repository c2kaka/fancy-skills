# Example Patterns

Use these patterns as reusable thinking tools, not as text to copy blindly.

## Pattern 1: Planner versus Runtime

Use this split when top-level routing and execution-time enrichment are currently mixed together.

- `Planner`: decides whether the request should enter a structured path
- `Router`: chooses the execution entry after planning or matching
- `Runtime`: enriches an already chosen path with context, evidence, retrieval, or tenant-specific rules

Helpful sentence pattern:

`Planner 负责决定是否进入某类能力路径，Runtime 负责在路径已确定后提供上下文增强，不负责改写顶层路由。`

## Pattern 2: Skill category separation

Use this when a system has multiple kinds of skills or capability descriptors.

- `Planner skill`: entry-point orchestration intent
- `Agent skill`: single-agent adaptation and parameter preparation
- `Runtime skill`: execution-time context enrichment or policy-aware helper

Helpful sentence pattern:

`这三类 skill 不是重复建模，而是对应任务入口、主执行能力和运行时增强三个不同层级。`

## Pattern 3: Server-authoritative execution

Use this when the design must limit what the model is allowed to decide.

- The model may propose an intent or business parameters
- The server validates the intent against a whitelist
- The server controls executable templates, operators, entrypoints, and permissions

Helpful sentence pattern:

`LLM 只负责在受限空间内选择意图和业务参数，真正可执行的模板、入口和权限边界仍由服务端控制。`

## Pattern 4: Shared context injection

Use this when multiple downstream steps need the same derived context.

- Create a typed context object or shared data payload
- Record its source and version
- Inject it into the steps that need it
- Revalidate high-impact fields at each consumer

Helpful sentence pattern:

`上下文透传是可选增强，不替代下游节点自身校验。`

## Pattern 5: Rollout by contract stabilization

Use this when the system already has partial implementations.

- `P0`: normalize config, schema, and validation boundaries
- `P1`: adapt main execution paths without deleting compatibility layers too early
- `P2`: unify observability, registry, UI, and evaluation

Helpful sentence pattern:

`先固化边界和契约，再逐步统一执行链路与观测能力，避免在行为仍不稳定时过早抽掉兼容层。`
