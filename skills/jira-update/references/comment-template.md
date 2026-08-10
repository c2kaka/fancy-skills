# JIRA repair comment template

Use plain JIRA-compatible text. Keep this heading and bullet order. Fill every bullet from the repair handoff; do not invent evidence.

```text
修复结果

- 稳定复现：<复现场景、至少两次一致失败、清理后的预期状态与实际失败状态>
- 根因：<连接稳定复现与责任代码路径的因果证据>
- 确认的解决方案：<用户明确批准的解决方案及关键数据流变化>
- 实际修改：<行为变化，以及修改的文件或模块摘要>
- 回归测试：修复前 <测试或命令> 因预期原因失败；修复后通过。<相关测试通过数量>
- 其他验证：<聚焦与扩大验证结果；如有无关基线失败或全量检查既有错误，明确区分>
- 本地 Commit：<hash> <subject>
```

Do not add a `剩余风险` bullet to the default JIRA comment. Keep limitations and unverified acceptance items in the repair handoff and final user report. Do not put credentials, private local paths, raw secret-bearing logs, or temporary attachment paths in the comment. Do not state that JIRA was reassigned or transitioned; those operations happen after comment approval and are verified separately.
