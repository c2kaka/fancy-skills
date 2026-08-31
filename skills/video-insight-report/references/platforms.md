# Platform acquisition

Read this reference whenever a report needs platform access. Success means non-empty, validated content and usable media, not a zero exit code or an installed tool.

## Shared preflight

Run:

```bash
agent-reach doctor --json
python3 scripts/acquire_video.py preflight --url "<url>"
```

Do not read browser cookies, auto-login, bypass access controls, or reuse authenticated/private content. Stop with `BLOCKED` when public access is insufficient.

## YouTube

Use `yt-dlp` only for YouTube:

1. Metadata: `yt-dlp --dump-single-json --no-playlist`.
2. Subtitles: manual and automatic subtitles with preferred source/user languages.
3. Browser transcript fallback: OpenCLI, only after the `yt-dlp` subtitle response is empty or unavailable. Retry an explicitly empty expiring-caption response at most three times.
4. No usable subtitles: download public media/audio and use local transcription.
5. Frames: extract from the downloaded video with `ffmpeg`.

Validate that the selected URL resolves to one video. Shorts are acceptable only when they resolve as a normal public item; playlists and multi-video aggregation are out of scope.

## Bilibili

Never invoke `yt-dlp` directly with a Bilibili URL; current platform protection can return 412 even with cookies.

Use:

1. Metadata/subtitle availability: `bili video <BV-or-url> --json`.
2. Timeline subtitles: `opencli bilibili subtitle <BV-or-url> -f json`, with `bili video --subtitle-timeline` as a read-only fallback.
3. No subtitles: `bili audio <BV-or-url> --no-split --output <run-dir>` followed by local transcription.
4. Video file for frames: `opencli bilibili download <bvid> --output <run-dir> --quality 720p -f json` through a public ephemeral browser session.

The OpenCLI download adapter currently describes an internal `yt-dlp` dependency while Agent Reach forbids direct Bilibili use of `yt-dlp`. Treat the adapter as unverified until its output contains a non-empty playable video and a frame can be extracted. Do not substitute a cover or player screenshot if it fails.

## Acquisition commands

Use `scripts/acquire_video.py` for deterministic command construction, safe output directories, output validation, and redacted results:

```bash
python3 scripts/acquire_video.py metadata --url "<url>" --run-dir "<dir>"
python3 scripts/acquire_video.py subtitles --url "<url>" --run-dir "<dir>"
python3 scripts/acquire_video.py video --url "<url>" --run-dir "<dir>" --allow-download
python3 scripts/acquire_video.py audio --url "<url>" --run-dir "<dir>" --allow-download
```

Subtitle acquisition returns an `attempts` array with each adapter's exit code, whether it produced a usable timeline, and a redacted diagnostic. Preserve these separate observations: an adapter reporting no subtitles and another requiring authentication are different evidence, even when the aggregate result is `UNAVAILABLE` with reason `no_usable_timeline`.

Run the download modes only after resource preflight. Never add `--force` for paid/private Bilibili content.
