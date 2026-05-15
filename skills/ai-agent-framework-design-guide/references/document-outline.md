# AI Agent / Skill / Runtime Framework Design Outline

Use this outline when the user asks for a formal framework design document or architecture proposal. Cut sections only when the task is intentionally small.

## Default structure

```markdown
# <文档标题>

版本：v0.1
日期：<YYYY-MM-DD>
适用范围：<系统、模块、能力边界>

## 1. 设计目标

- 这份设计要统一什么
- 解决当前哪些断层、耦合、不可解释或不可扩展问题
- 本次明确不做什么

## 2. 现状依据

### 2.1 已有机制

- 当前有哪些模块、流程、配置或协议
- 哪些行为来自代码事实，哪些来自已有文档

### 2.2 当前问题与约束

- 当前痛点
- 兼容性要求
- 不能突破的边界

## 3. 总体架构

- 分层结构
- 每层职责
- 各层之间的数据或控制关系
- 需要时给出 Mermaid 图

## 4. 核心配置或接口设计

- 关键 schema
- 配置字段说明
- 约束与校验原则

## 5. 调用逻辑

- 主链路时序
- 路由条件
- 执行入口
- 返回结果与停止条件

## 6. 各类能力或 Skill 处理流程

- Planner / Router / Agent / Runtime 等分类处理
- 每类的输入、选择、执行和输出

## 7. 运行时增强、参数透传与上下文注入

- 上下文从哪里来
- 传到哪里去
- 哪些字段可透传
- 哪些地方必须二次校验

## 8. 安全、降级与可观测性

- 服务端边界
- 非法输入拦截
- 回退策略
- 审计与日志字段

## 9. 推荐落地路径

- P0：先规范什么
- P1：再接什么
- P2：最后统一什么

## 10. 风险与开放问题

- 只列真正影响设计成败的点
- 区分已决定与待确认事项

## 11. 结论

- 用 1 到 3 段总结框架边界、价值和下一步
```

## When to compress

- 如果只是补一段设计说明，可以合并 `4/5/6`。
- 如果重点是运行时增强，可以把 `3/4/5` 围绕 Runtime 展开，不必平均用力。
- 如果用户只要方案，不要落地计划，可以保留 `9` 为简版，但不要完全省掉。

## Recommended document habits

- 在标题下方给出版本、日期、适用范围。
- 对重要章节用 "现状 / 建议 / 约束 / 结论" 这样的稳定语义。
- 图只画帮助理解的主路径，不用为完整而完整。
