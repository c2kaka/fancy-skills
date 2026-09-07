# 本地任务邮件

Python 3 标准库脚本，固定收件人为 `fanoykaka@outlook.com`，不支持附件或额外收件人。默认只预览；传入 `--send` 才发送。支持 SMTP over TLS 和 STARTTLS，始终校验证书。

## 本机配置

1. 将 `config.example.json` 复制到 `~/.config/codex-mail/config.json`（先创建目录），填写发件服务实际提供的 SMTP 主机、端口、账号和发件地址。`security` 仅接受 `ssl` 或 `starttls`；示例地址不能用于发送。建议目录权限 700、配置文件权限 600。
2. 在 macOS「钥匙串访问」中创建一个密码项目：项目名称为 `codex-task-mail`，账户与配置中的 `username` 完全一致，密码填写服务提供的 SMTP 密码或应用授权码。不要将密码写入 JSON、命令行参数、聊天或仓库。首次读取可能弹出钥匙串授权提示，由用户在本机处理。
3. 使用下方命令预览，再加 `--send` 发送测试邮件，并检查收件箱。

该实现使用 SMTP 账号/密码认证。只支持 OAuth 的邮件账户不能直接使用；需要另行实现该服务的 OAuth 授权和令牌刷新，或选择提供 SMTP 凭证的发件服务。收件邮箱是 Outlook 不代表发件方必须使用 Outlook。具体服务器参数和认证政策应以发件服务当前文档为准。

## 调用

```bash
python3 /Users/ouyangfan/AI/fancy-skills/tools/local-mail/send_mail.py \
  --subject 'Codex 任务完成' --body-file /absolute/path/to/notification.txt
```

确认内容后，在同一命令末尾添加 `--send`。也可省略 `--body-file`，通过标准输入提供正文。不要包含凭证、原始日志或完整项目文件。自定义配置路径用 `--config /absolute/path/config.json`。

输出为 JSON：`preview` 表示未发送；`accepted` 表示 SMTP 服务已接受，但不保证最终投递；`rejected` 表示明确拒绝；`not_sent` 表示发送前失败；`unknown` 表示发送过程中连接等异常，可能已经投递。退出码分别为 0（预览/接受）、1（失败/拒绝）、2（结果不确定）。脚本不自动重试；`unknown` 时先检查收件箱或服务记录，避免重复通知。

供 Codex 的全局规则引用：

> 任务通知使用 `/Users/ouyangfan/AI/fancy-skills/tools/local-mail/send_mail.py`，配置为 `~/.config/codex-mail/config.json`。正文通过 UTF-8 文件或标准输入传入，实际发送使用 `--send`。只在已有通知授权范围内调用；依据 JSON 状态报告结果，结果不确定时不得盲目重发。

脚本本身不创建自动通知或修改全局规则。配置和钥匙串准备好后，Codex 可从任意工作目录调用绝对路径。
