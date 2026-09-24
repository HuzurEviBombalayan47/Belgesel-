# Chronicle AI — Documentary Video Studio (living spec)

Stage 1 = **foundation**. One audio upload becomes a project with a professional
documentary-style, multi-lane timeline. AI scene planning, asset search, animation,
SFX and rendering are architectural seams, not implementations.

## What the app does today

1. User uploads ONE audio file (drag/drop or browse) on `/`.
2. The browser decodes the real samples into a 2000-point peak envelope (waveform)
   and reports the decoded duration.
3. Backend validates type/size, spools to a temp file, probes the real duration with
   `mutagen`, uploads the original bytes to **Cloudflare R2**, and inserts the project.
4. Whisper (`whisper-1`, via `EMERGENT_LLM_KEY`) transcribes in a background task →
   timestamped `transcript_segments` rows. The editor polls until ready.
5. `/projects/:id` is the editor: transport (play/pause, ±5s, SMPTE timecode),
   zoomable multi-lane timeline (ruler, playhead, scenes lane, transcript lane,
   waveform lane), transcript inspector with clickable timestamps, scenes roadmap
   panel, and a **Render video** button that honestly reports stage 2.

## Data model (MongoDB)

| collection | shape | notes |
|---|---|---|
| `projects` | `models/projects.py::Project` | `audio` sub-doc holds `object_key`, `duration_seconds`, `waveform`; `transcription` holds status/error/segment_count/language/model |
| `transcript_segments` | `models/timeline.py::TranscriptSegment` | `project_id`, `index`, `start_seconds`, `end_seconds`, `text` |
| `scenes` | `models/timeline.py::Scene` | written by the stage-2 scene planner; `treatment` ∈ ken_burns/archival_photo/map/chart/motion_typography/stock_footage/title_card |
| `render_jobs` | `models/renders.py::RenderJob` | written by the stage-2 render pipeline |

Ids are string uuid4. Datetimes stored aware-UTC, normalised on read.

## API (all on `api_router`, prefix `/api`)

- `GET  /system/status` → storage configured?, transcription configured?, upload limit
- `POST /projects` (multipart: `file`, optional `title`, `peaks`, `client_duration`) → 201 Project
- `GET  /projects` → ProjectSummary[]
- `GET  /projects/{id}` → Project (404 if unknown)
- `DELETE /projects/{id}` → removes R2 object + all child rows
- `POST /projects/{id}/analyze` → re-run transcription (downloads audio back from R2)
- `GET  /projects/{id}/audio` → range-aware audio stream (206 on Range)
- `GET  /projects/{id}/transcript` → TranscriptSegment[]
- `GET  /projects/{id}/scenes` → Scene[] (empty in stage 1)
- `POST /projects/{id}/renders` → **501** FeatureDisabled (honest; never a fake success)
- `GET  /projects/{id}/renders` → RenderJob[]

Error contract: 415 unsupported type, 413 too large, 404 unknown project,
410 object missing in storage, 501 disabled seam, **424 storage failure or storage not
configured** (deliberately not 502/503 — the platform ingress replaces gateway-class
response bodies with its own error page, which hides the real message from the UI).

## Upload internals (large files)

- `lib/storage.py` uploads ≤32 MB as a single `put_object` and larger files through
  boto3's managed **multipart** transfer (`TransferConfig`, 16 MB parts). A plain
  `upload_file` on an endpoint without multipart support raised `KeyError: 'UploadId'`
  — the original cause of the reported 502.
- Botocore failures are translated by `describe_storage_error()` into actionable
  sentences (bad access key, signature mismatch, missing bucket, unreachable endpoint,
  non-compliant S3 response) and returned as the `detail` of a 424.
- `lib/audio_prep.py` keeps **real** transcription working past the API's 25 MB cap:
  an oversized WAV is downmixed to 16 kHz mono and, if still too large, split into
  sequential chunks whose segment timestamps are offset back onto the original
  timeline. Compressed formats over the cap fail with an explicit message (no
  in-pod decoder). Verified: a 48 MB / 26-minute WAV produced 221 segments spanning
  the full 1579 s.

## Architecture seams for stage 2

- `services/transcription.py` — real Whisper impl behind a `TranscriptionService`
  Protocol. >24 MB raises `AudioTooLargeForTranscription` (chunking = stage 2).
- `services/scene_planner.py` — `ScenePlanner` Protocol; stage 1 registers
  `DisabledScenePlanner` which raises `FeatureDisabled`. Stage 2 implements `plan()`
  → writes `scenes` rows; the timeline lane already renders them.
- `rendering/pipeline.py` — `RenderEngine` Protocol; stage 1 registers
  `DisabledRenderEngine`. Stage 2 adds the compositor (Ken Burns, maps, charts,
  kinetic type, transitions, SFX) behind the same `submit()` signature.
- `lib/storage.py` — R2-only object storage (S3 API, path-style, boto3 in threads).
  **No local-disk fallback by design**; missing keys → `StorageNotConfigured` → 503.
  `presigned_get()` is ready for direct-CDN playback later.

## Storage configuration

`backend/.env`: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
`R2_BUCKET`, optional `R2_ENDPOINT_URL`.

> **Current state:** the user has not supplied real R2 keys yet, so `.env` points
> `R2_ENDPOINT_URL` at a local S3-compatible stub (`/tmp/s3stub.py`, port 9000) purely
> so the R2 code path could be verified end-to-end. Swapping in real Cloudflare keys and
> deleting `R2_ENDPOINT_URL` is the only change needed — no code edits.

## Verified (stage 1 gate, through the public URL)

upload → R2 write → duration probe → Whisper transcript with timestamps → poll to
`ready` → range-aware playback (206) → timeline/transcript render → 415/404/501
negative cases.

## Not implemented (deliberately)

AI scene planning, asset search/ingest, animations, SFX, video rendering/export.
No demo/seed projects — the app shows real user data only.
