---
name: my-jira-query
description: Query a JIRA issue from the configured server and return its summary, type, status, priority, reporter, assignee, components, labels, fix versions, environment, description, attachments, and comments. Use when a user asks to query, inspect, summarize, or understand a JIRA issue such as JIRA-1234 without modifying it.
---

# My JIRA Query

Query JIRA through the bundled read-only Python script. Resolve all paths relative to this `SKILL.md`; do not assume the caller's working directory.

## Configure

Require `<skill-directory>/.env` with exactly these settings:

```dotenv
JIRA_BASE_URL=https://jira.example.com
JIRA_USER=your-jira-username
JIRA_PASSWORD=your-jira-password
```

If `.env` is missing, copy `.env.example` to `.env`, ask the user to fill in the credentials locally, and stop. Never ask the user to paste a password into chat. Never print, log, or return `.env` contents.

The repository ignores `.env`; `.env.example` contains only safe placeholders.

## Query an issue

Extract the issue key from the user's request, then run:

```bash
python3 <skill-directory>/scripts/query_jira.py JIRA-1234
```

Options:

- `--json`: print the original API response when full fields are required.
- `--comments 0`: omit comments from formatted output.

Return the query result and, when useful, a concise summary. Treat attachment URLs as references; do not download attachments unless the user asks.

## Handle failures

- Missing or invalid `.env`: report the exact configuration problem without exposing values.
- HTTP 401: ask the user to verify the local JIRA username and password.
- HTTP 404: ask the user to verify the issue key and access permissions.
- Network failure: ask the user to check the JIRA URL, VPN, and network access.

This skill is read-only. Do not transition, edit, comment on, or reassign the issue.
