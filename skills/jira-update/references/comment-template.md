# JIRA repair comment template

Use plain JIRA-compatible text. Omit empty optional details rather than inventing them.

```text
修复结果

- 稳定复现：<controlled reproduction and repeated failure evidence>
- 根因：<evidence-backed causal explanation>
- 确认的解决方案：<solution explicitly approved by the user>
- 实际修改：<changed behavior and concise file/module summary>
- 回归测试：修复前 <test/command> 失败；修复后通过
- 其他验证：<focused and broader checks, including baseline failures if any>
- 本地 Commit：<hash> <subject>
- 剩余风险：<known limits or “无已知剩余风险” when supported by evidence>
```

Do not put credentials, private local paths, raw secret-bearing logs, or temporary attachment paths in the comment. Do not state that JIRA was reassigned or transitioned; those operations happen after comment approval and are verified separately.
