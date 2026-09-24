# Chronicle AI — Documentary Video Studio (living spec)

**Stage 1 (done):** audio upload → Cloudflare R2 → real Whisper transcript with
timestamps → multi-lane documentary timeline.
**Stage 2 (this build):** an AI Scene Planner turns the transcript into structured
visual scene plans that appear on the timeline and in an inspector.
**Stage 3 (next):** resolve each scene's `visual_search_queries` into real internet
assets. **Stage 4:** timeline rendering/compositing.

## What the app does today

1. User uploads ONE audio file on `/`; the browser decodes real samples into a
   2000-point waveform and reports decoded duration.
2. Backend validates, probes real duration (`mutagen`), stores the original bytes in
   **Cloudflare R2** (single PUT ≤32 MB, managed multipart above), inserts the project.
3. Whisper (`whisper-1`) transcribes in a background task → timestamped
   `transcript_segments`. Oversized WAVs are downmixed to 16 kHz mono and chunked, with
   chunk timestamps offset back onto the real timeline.
4. **"Analyze & Create Scenes"** runs the AI Scene Planner over the transcript →
   `scenes` rows → coloured blocks on the timeline's scenes lane + a scene list, each
   openable in a full inspector.
5. **Render video** is honest: asset search and the compositor are later stages, so
   `POST /renders` answers 501 and the dialog says so.

## Data model (MongoDB)

| collection | shape | notes |
|---|---|---|
| `projects` | `models/projects.py::Project` | `audio`, `transcription`, **`scene_planning`** (status/error/scene_count/model/progress) |
| `transcript_segments` | `TranscriptSegment` | `project_id`, `index`, `start_seconds`, `end_seconds`, `text` |
| `scenes` | `models/timeline.py::Scene` | the structured visual plan — see below |
| `render_jobs` | `models/renders.py::RenderJob` | written by a later stage |

### Scene (the stage-3 contract)

`start_time`, `end_time`, `transcript_text`, `scene_type`, `visual_goal`,
`visual_search_queries[]`, `suggested_visual_treatment`, `important_text[]`,
`animation_type`, `transition_type`, `sound_effect_suggestion`, plus `id`,
`project_id`, `index`, `status`, `asset_ids[]` (empty — no assets are fetched yet).

`scene_type` ∈ PHOTO · VIDEO · HISTORICAL_IMAGE · DOCUMENT · MAP · CHART ·
TEXT_ANIMATION · MOTION_GRAPHIC · LOGO · SCREENSHOT · MIXED.

## API (all on `api_router`, prefix `/api`)

- `GET  /system/status` → storage / transcription / **scene_planning** capability + model
- `POST /projects` (multipart `file`, optional `title`, `peaks`, `client_duration`) → 201
- `GET  /projects` · `GET /projects/{id}` · `DELETE /projects/{id}`
- `POST /projects/{id}/analyze` → re-run transcription (re-downloads audio from R2)
- `GET  /projects/{id}/audio` → range-aware stream (206 on Range)
- `GET  /projects/{id}/transcript` → TranscriptSegment[]
- `GET  /projects/{id}/scenes` → Scene[]
- **`POST /projects/{id}/scenes/plan`** → 202, starts the AI pass (409 if the transcript
  isn't ready or a pass is already running; 424 if no AI key is configured)
- **`DELETE /projects/{id}/scenes`** → discard the plan so it can be re-run
- `POST /projects/{id}/renders` → 501 (later stage) · `GET .../renders` → RenderJob[]

Error contract: 415 unsupported type, 413 too large, 404 unknown project, 409 wrong
state, 410 object missing in storage, 501 not-yet-built stage, **424 dependency failure
or missing configuration** (deliberately not 502/503 — the ingress replaces
gateway-class bodies with its own page, hiding the real message).

## AI Scene Planner (`services/scene_planner.py`)

- Provider/model from env: `SCENE_PLANNER_PROVIDER` (default `gemini`),
  `SCENE_PLANNER_MODEL` (default `gemini-2.5-flash`).
- Key precedence: **`GEMINI_API_KEY`** (user's own Google key, used directly) →
  `EMERGENT_LLM_KEY`. Keys live only in `backend/.env`, never reach the frontend.
- The transcript is planned in windows of 18 segments with concurrency 3; windows are
  merged in order, de-overlapped and re-indexed.
- Every scene is validated against the Pydantic model. Generic search queries
  ("cinematic background", "corporate b-roll", …) are stripped, and a scene lacking a
  goal or treatment is dropped rather than padded.
- Any total failure raises `ScenePlanningError`, recorded on
  `project.scene_planning` as `failed` + the actual provider message. **No placeholder
  or fabricated scenes are ever written.**
- Runs as a background task; the editor polls `scene_planning` for progress.

## Configuration

`backend/.env`: `MONGO_URL`, `DB_NAME`, `CORS_ORIGINS`, `MAX_UPLOAD_MB`,
`EMERGENT_LLM_KEY`, optional `GEMINI_API_KEY`, `SCENE_PLANNER_MODEL/PROVIDER`,
and R2: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`,
optional `R2_ENDPOINT_URL`.

> **Current state (2 open items):**
> 1. The user supplied an R2 access key + secret but not the Account ID or bucket name,
>    so `R2_ENDPOINT_URL` still points at the local S3-compatible endpoint
>    (`tools_local_s3_stub.py`, supervisor program `localstoragestub`, objects under
>    `/app/.local-object-store`). It implements multipart exactly like R2; swapping in
>    the real account id + bucket needs no code change.
> 2. The Emergent universal key's budget is exhausted (429 `budget_exceeded`), so the
>    planner cannot execute until the user pastes a `GEMINI_API_KEY` or tops up credits.
>    The failure path is verified: explicit error, zero scenes.

## Not implemented (deliberately)

Asset search/download, animations, SFX, video rendering/export. No demo/seed projects.
`tools_seed_demo_scenes.py` is a verification-only tool (clearly-labelled seeded rows,
never presented as AI output) — not imported by the app.
