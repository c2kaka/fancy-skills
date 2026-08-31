# Local transcription

Read this reference only when no reliable subtitles exist.

## Baseline

The local baseline is `mlx-whisper` on Apple Silicon. It runs on device and supports JSON plus word-level timestamps. The default model is configurable; the script defaults to `mlx-community/whisper-large-v3-turbo` for a quality/speed balance.

Run preflight first:

```bash
python3 scripts/local_transcribe.py preflight
```

If the package or model is missing, report the model identifier, cache location, and that a download is required. Obtain confirmation before running:

```bash
python3 scripts/local_transcribe.py transcribe \
  --audio "<audio-file>" \
  --output "<run-dir>/transcript.json" \
  --allow-model-download
```

Without `--allow-model-download`, the script must refuse a first download. The flag authorizes the package/model acquisition for that run only; it is not cloud-transcription authorization.

## Validation

`mlx_whisper` can catch an internal exception and continue, so do not trust its process exit code alone. Success requires:

- a parseable JSON result;
- at least one non-empty segment;
- numeric start/end timestamps with `end >= start`; and
- a final normalized transcript written atomically.

Low `avg_logprob`, high `no_speech_prob`, overlapping speech, or unintelligible terminology must remain uncertainty signals. Do not invent missing words.

## Cloud boundary

Cloud transcription is not a silent retry. Before using one, state the provider, audio scope, credential source, and cost risk, then obtain explicit authorization. Do not use `agent-reach transcribe --allow-provider-fallback` unless the user separately authorizes every provider that may receive the audio.
