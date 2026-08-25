---
name: jira-report-quality-issue
description: Review a coding agent's current delivery context, turn independently verified quality defects into evidence-backed JIRA drafts, preview exact issue and screenshot payloads, and create issues assigned to the authenticated account owner only after explicit approval. Use when the user explicitly asks to quality-check coding work and file one or more JIRA issues for themselves; never invoke implicitly for ordinary code review or bug fixing.
---

# JIRA Quality Issue Reporter

Review the current coding delivery before drafting anything. Create one JIRA issue per independent root cause only when the defect is evidenced, actionable, in scope, and not an unrelated baseline failure.

This skill performs external, non-transactional writes. Never run `apply` until the user approves the complete, unchanged creation packet.

## Keep responsibilities separate

Use model reasoning to:

- understand the task, acceptance criteria, diff, tests, logs, and relevant history;
- distinguish a confirmed defect from a suspicion, style preference, or unrelated baseline problem;
- group symptoms by independent root cause;
- compare JIRA candidates semantically rather than by keyword similarity;
- visually inspect every screenshot for relevance and sensitive content;
- write the draft and explain the proposed priority and fields.

Use `scripts/jira_quality_issue.py` only for deterministic validation, canonicalization, JIRA API calls, screenshot hashing, locking, state, and verification. Do not add regex, keyword lists, or fixed case patches to the script as a substitute for the reasoning above.

## Configure locally

Read credentials only from this skill's `.env`:

```dotenv
JIRA_BASE_URL=https://jira.example.com
JIRA_USER=your-jira-username
JIRA_PASSWORD=your-jira-password-or-api-token
JIRA_PROJECT_KEY=PROJECT
JIRA_ISSUE_TYPE=Bug
JIRA_COMPONENTS=["Your Component"]
JIRA_FIX_VERSIONS=["Your Fix Version"]
```

Require an HTTPS origin without credentials, path, query, or fragment. Keep `.env` ignored, blank until the owner configures it, and mode `600`. Never inspect or copy another skill's `.env`, expose credentials in output, or put credentials in command arguments.

Treat `JIRA_COMPONENTS` and `JIRA_FIX_VERSIONS` as JSON string-array defaults. Use them when an issue omits `components` or `fixVersions`; an explicitly supplied draft field overrides its default. Always validate the resolved values against live create metadata and include them in the approval fingerprint.

## Follow the guarded workflow

### 1. Audit the current delivery

Inspect the current user request, repository status, relevant diff, tests, runtime evidence, and necessary history. Stay within the current task and repository unless the user explicitly expands scope. Preserve unrelated dirty changes.

Create a finding only when all are true:

1. Evidence proves an actual/expected behavior gap.
2. The finding has an observable delivery, reliability, security, performance, data, or architecture impact.
3. It can be independently fixed and accepted.
4. It belongs to the current delivery rather than an unrelated baseline.
5. It is not a style nit or unsupported speculation.

When evidence is insufficient, report the missing evidence and stop at a non-creatable draft.

### 2. Prepare screenshots

Accept only explicit local files supplied or captured for the current task. Support PNG, JPEG, and WebP. Do not scan directories, browser caches, or unrelated tasks.

View every image directly. Reject it if it contains suspected credentials, tokens, private information, unrelated content, or unclear evidence. Do not auto-redact; ask the user for a sanitized screenshot. Record a useful description and visual-review note in the draft.

### 3. Build the draft

Read [references/draft-schema.md](references/draft-schema.md) completely. Create the JSON draft in a permission-restricted temporary directory. Use repository identity rather than a private absolute workspace path in `context.repository`. Use repository-relative paths in JIRA content.

Never invent a repository identity or use placeholders such as an unspecified repository. If the actual repository identity is unavailable, return a human-readable, non-creatable draft and list the missing fact; do not claim schema validation or run preflight.

Use a natural summary:

```text
<module or scenario>: <observable failure>
```

Do not add an agent-brand prefix. Separate facts, limitations, and suggested direction. Do not include secrets, `.env` content, raw authorization headers, hidden prompts, private temporary paths, irrelevant code, or model chain-of-thought.

Do not infer `priority`, `components`, `environment`, `fixVersions`, `labels`, or custom fields from semantic keywords. Include them only when the task context, project conventions, explicit configuration, or JIRA metadata provides an evidenced value. Otherwise use `null`, an empty list, or an empty object and explain the omission in the preview.

### 4. Run read-only preflight

```bash
python3 <skill-directory>/scripts/jira_quality_issue.py preflight --draft <draft.json>
```

Preflight reads JIRA but never writes. It verifies deployment type, authenticated identity, project, issue type, permissions, required fields, attachment settings, screenshot bytes, existing fingerprints, and unresolved duplicate candidates.

If duplicate candidates exist, inspect their evidence semantically. Add the exact returned `candidateDigest` and the decision to each issue's `duplicateReview`, then rerun preflight. Never automatically decide from summary similarity.

The duplicate snapshot is semantic: its digest covers candidate key, summary, and status in stable order. Timestamp-only updates and result-order changes do not invalidate an approval; candidate additions, removals, summary changes, and status changes do.

If preflight returns a blocker, resolve it and rerun. Do not bypass metadata, permissions, identity, duplicate, or screenshot failures.

### 5. Present one complete approval packet

Show the user, for every planned issue:

- project, issue type, summary, full description, priority, components, environment, Fix Versions, labels, and custom fields;
- authenticated reporter and self-assignee identity;
- duplicate candidates and the chosen decision;
- every screenshot preview, source, upload name, MIME type, dimensions, size, SHA-256, and target issue;
- exact issue count and sequential operation order;
- batch fingerprint;
- the warning that issue creation and attachment upload are non-transactional.

Explain that execution stops on the first failure, never deletes completed issues, and never blindly retries a POST. Wait for explicit approval of this exact packet. General permission from an earlier conversation or approval of a different fingerprint does not count.

### 6. Bind and apply the approval

After approval, add the exact preflight fingerprint to the temporary draft as `approvedBatchFingerprint`. Do not change any other field or screenshot.

```bash
python3 <skill-directory>/scripts/jira_quality_issue.py apply \
  --draft <draft.json> \
  --confirm <approved-batch-fingerprint>
```

The command rejects an initial confirmation mismatch before reading credentials. It then reruns preflight; any remote metadata, candidate, field, or screenshot change invalidates the approval.

Apply processes issues sequentially. For each new issue it performs one create POST, a GET field verification, one upload POST per approved screenshot, and a final attachment GET. It never uses bulk create.

### 7. Handle partial or unknown outcomes

Treat these as incomplete, never successful:

- `created_but_unverified`
- `creation_outcome_unknown`
- `attachment_outcome_unknown`
- `attachment_ambiguous`
- `partial`

Stop immediately. Report completed issue keys, verified screenshots, failed step, and remaining work. Never automatically retry, delete, comment, change the description, or create a replacement issue.

Use read-only recovery first:

```bash
python3 <skill-directory>/scripts/jira_quality_issue.py verify --operation <operation-id>
```

For a definitely missing attachment only, `verify` returns a `resumePlan` and `resumeFingerprint`. Reconstruct the original draft, verify its batch and screenshot hashes, present that exact attachment-only plan, add `approvedResumeFingerprint`, obtain explicit approval, then run:

```bash
python3 <skill-directory>/scripts/jira_quality_issue.py apply \
  --operation <operation-id> \
  --draft <draft.json> \
  --resume-attachments \
  --confirm <approved-resume-fingerprint>
```

Do not resume an attachment whose remote outcome is unknown or ambiguous.

### 8. Report verified results

Report each issue key and clickable URL, final fields, reporter, assignee, attachments, fingerprint, completed steps, differences, and unexecuted steps. Call the batch `verified` only when every approved field and screenshot passes the final GET.

Local state contains no credentials or screenshot copies. Keep partial, unknown, and unverified state. Clean only a verified operation when the user explicitly requests it:

```bash
python3 <skill-directory>/scripts/jira_quality_issue.py cleanup --operation <operation-id>
```

## Preserve external-write boundaries

- Never use this skill implicitly.
- Never access real JIRA during skill development or testing without separate authorization.
- Never create a disposable test issue merely to test the skill.
- Never treat browser login as REST credential proof.
- Never follow redirects with credentials.
- Never claim byte-level remote screenshot verification; JIRA exposes attachment metadata, not a content hash.
- Never commit or push repository changes unless the user separately asks.
