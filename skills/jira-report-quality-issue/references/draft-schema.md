# Draft schema

Read this file before creating or editing a draft. The script accepts schema version `1` only.

## Shape

```json
{
  "schemaVersion": 1,
  "context": {
    "repository": "org/repository",
    "branch": "feature/example",
    "commit": "optional-commit-sha",
    "task": "Describe the coding delivery being reviewed"
  },
  "projectKey": "OPTIONAL_ENV_OVERRIDE",
  "issueType": "OPTIONAL_ENV_OVERRIDE",
  "issues": [
    {
      "summary": "Module: observable failure",
      "description": {
        "background": "Task goal and relevant context",
        "actualBehavior": "What is observably wrong",
        "expectedBehavior": "What acceptance requires",
        "impact": "Who or what is affected and how",
        "reproductionSteps": ["Step 1", "Step 2"],
        "evidence": ["Repository-relative path, test, log, or runtime evidence"],
        "affectedScope": ["Repository-relative module or contract boundary"],
        "verification": ["Checks already run and their factual result"],
        "limitations": ["Anything relevant that remains unverified"],
        "suggestedDirection": "Evidence-backed direction, not a mandatory solution"
      },
      "priority": "Optional JIRA priority name",
      "components": [],
      "environment": "Optional environment name, version, and relevant URL",
      "fixVersions": [],
      "labels": [],
      "customFields": {},
      "qualityReview": {
        "approved": true,
        "notes": "Why this is a confirmed, actionable, in-scope defect rather than a baseline or nit"
      },
      "safetyReview": {
        "approved": true,
        "notes": "Why the text is necessary and contains no secrets or private local context"
      },
      "screenshots": [
        {
          "path": "/explicit/local/path/evidence.png",
          "description": "What the screenshot proves",
          "visualReview": {
            "approved": true,
            "notes": "Viewed directly; relevant and no suspected sensitive content"
          }
        }
      ],
      "duplicateReview": null
    }
  ]
}
```

`projectKey` and `issueType` may be omitted to use `.env` defaults. `components` and `fixVersions` may also be omitted to use the JSON arrays in `JIRA_COMPONENTS` and `JIRA_FIX_VERSIONS`. An explicitly supplied issue field, including an empty array, overrides its `.env` default. All issues in one batch share the resolved project and issue type. Use separate batches for different targets.

`commit` and `branch` may be `null` when unavailable. `repository` and `task` are required and must not expose a private absolute path. `repository` must be a factual stable identity from the current workspace, such as its remote identity or established repository name. Never invent a value or use an `unspecified` placeholder merely to satisfy the schema. Without that fact, stop with a human-readable, non-creatable draft and do not run the script.

## Description rules

All scalar description fields are required non-empty strings. All list fields must be arrays of non-empty strings. `limitations` may be empty; other description lists must contain evidence.

Use facts in `actualBehavior`, `expectedBehavior`, `impact`, `reproductionSteps`, and `evidence`. Keep uncertainty in `limitations`. Do not present `suggestedDirection` as a proven fix.

Use only `customfield_<id>` keys in `customFields`. Preflight checks them against the target create metadata. Never invent a value for a required custom field.

Do not derive `priority`, `components`, `environment`, `fixVersions`, `labels`, or custom-field values from a keyword list or generic conventions. Use only values evidenced by the task, repository conventions, explicit configuration, or live JIRA metadata. Leave optional values empty when no source exists. Preflight validates every supplied Fix Version against create metadata.

## Duplicate review cycle

The first preflight may return `duplicate_review_required` with a candidate list and `candidateDigest`. Inspect candidates semantically. Then set one of:

```json
{
  "candidateDigest": "exact-value-from-preflight",
  "decision": "no-duplicate",
  "existingIssueKey": null,
  "justification": "Explain why the root cause or affected behavior differs"
}
```

```json
{
  "candidateDigest": "exact-value-from-preflight",
  "decision": "use-existing",
  "existingIssueKey": "PROJECT-123",
  "justification": "Explain why this existing issue covers the finding"
}
```

```json
{
  "candidateDigest": "exact-value-from-preflight",
  "decision": "create-despite-candidate",
  "existingIssueKey": null,
  "justification": "Explain the independent root cause or acceptance boundary"
}
```

Rerun preflight after changing the decision. A changed candidate snapshot invalidates the review.

Candidate snapshot identity is based on candidate key, summary, and status in stable order. Changes only to `updated` timestamps or search-result order do not change `candidateDigest`; additions, removals, summary changes, and status changes do.

## Approval fields

Do not add an approval field before the user approves the complete preflight packet. After approval, add:

```json
"approvedBatchFingerprint": "exact-batch-fingerprint"
```

This field is not part of the canonical payload, so adding it alone does not change the batch fingerprint.

For an approved attachment-only recovery, add:

```json
"approvedResumeFingerprint": "exact-resume-fingerprint"
```

The recovery command also requires the original `approvedBatchFingerprint`, unchanged issue content, and screenshot files with the original hashes.
