# Report contract

Read this reference before populating or changing `report.json`. The JSON manifest is authoritative; `report.html` is a deterministic view.

## Required top-level fields

```json
{
  "schema_version": "1.0",
  "skill_version": "0.1.0",
  "status": "INCOMPLETE",
  "source": {},
  "request": {},
  "pyramid": {},
  "chapters": [],
  "evidence": [],
  "first_principles": {},
  "uncertainties": [],
  "pipeline": {},
  "generation": {}
}
```

Use `scripts/video_insight.py init` to create a valid starting manifest and `render`/`validate` to enforce the full contract.

## Source and request

- `source`: `platform`, `video_id`, canonical `url`, `title`, `creator`, `duration_seconds`, and detected language when known.
- `request`: non-empty `questions`, `depth` (`concise`, `standard`, or `deep`), and `output_language`.
- The renderer includes built-in interface labels for Chinese (`zh-*`) and English. For another output language, the model may add a `request.ui_labels` object containing translated string overrides for the existing renderer label keys. Values remain untrusted text and are HTML-escaped; unknown keys and blank or non-string values are ignored. Report content itself is still authored in `output_language` regardless of interface-label overrides.

## Pyramid and chapters

- `pyramid.top`: the one-sentence answer.
- `pyramid.supports`: ordered objects with `title`, `summary`, and `evidence_ids`.
- `chapters`: ordered `start_seconds`, `end_seconds`, `title`, and `summary` entries covering the global video structure, not only the requested topic.

## Evidence

Each evidence object has a stable `id`, `claim`, `start_seconds`, `end_seconds`, a short `quote` when available, `quote_kind`, optional `speaker`, `confidence`, `raw_image`, optional `derived_image`, `rationale`, and `source_kind`.

- `raw_image` and `derived_image` are report-directory-relative paths.
- Each image record includes `path`, `sha256`, `width`, `height`, and `mime_type`.
- `confidence` is `high`, `medium`, or `low`. Low-confidence evidence cannot be the only evidence for a pyramid support.
- `quote_kind` distinguishes `subtitle`, `transcript`, `on_screen_text`, and `none`.
- `extract-frames` keeps unverified plan text under `planned_quote`/`planned_quote_kind` and leaves authoritative `quote` empty. After visual/transcript review, the model must explicitly promote only the verified wording into the manifest evidence record.

## First principles

Populate `problem`, `fundamentals`, `assumptions`, `mechanism`, `boundaries`, `rebuilt_conclusion`, `implications`, and `open_questions`. Keep video claims and model reconstruction distinct.

## Pipeline and state

`pipeline.stages` records `metadata`, `captions`, `transcription`, `frames`, `analysis`, `render`, and `validation`. Each stage records a status and may record paths, commands, or a redacted diagnostic. Do not store credentials, cookies, signed URLs, or full private paths that are not needed for recovery.

## Output layout

Default to:

```text
video-reports/<platform>-<video-id>-<question-hash>/
├── report.json
├── report.html
└── evidence/
    ├── raw/
    └── derived/
```

Temporary media belongs in the run's temporary acquisition directory and is removed after a successful report unless cache retention was explicitly requested.
