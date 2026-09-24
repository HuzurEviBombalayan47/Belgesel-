"""Project lifecycle: upload audio -> project created -> stream playback -> delete.

Upload pipeline (all real processing, no mocked states):
1. validate type/size, spool the upload to a temp file
2. probe duration server-side (mutagen reads the real container)
3. upload the original file to Cloudflare R2 via the storage layer
4. insert the project (status "ready" — the audio is stored and playable)
5. in the background: Whisper transcription -> transcript segments (the editor polls)

Long-running work never blocks the request: transcription is a background task whose
progress is observed through project.transcription.status.
"""

import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

from botocore.exceptions import ClientError
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from lib.db import db
from lib.media import (
    guess_content_type,
    is_allowed_upload,
    max_upload_bytes,
    probe_duration,
    sanitize_filename,
)
from lib.storage import StorageNotConfigured, get_storage, iter_body
from models.projects import AudioAsset, Project, ProjectSummary, TranscriptionInfo, utcnow
from models.timeline import TranscriptSegment
from services.transcription import (
    AudioTooLargeForTranscription,
    get_transcription_service,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_READ_CHUNK = 512 * 1024


class _UploadTooLarge(Exception):
    pass


async def project_or_404(project_id: str) -> Project:
    doc = await db.projects.find_one({"id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="project not found")
    return Project(**doc)


async def _update(project_id: str, **fields) -> None:
    update: dict = {"updated_at": utcnow()}
    for key, value in fields.items():
        update[key] = value.model_dump() if hasattr(value, "model_dump") else value
    await db.projects.update_one({"id": project_id}, {"$set": update})


def _parse_peaks(raw: str | None) -> list[float] | None:
    """Client-computed peak envelope (real samples, decoded in the browser).
    Accepted only when it parses as a bounded list of numbers; clamped to 0..1."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, list) or not data or len(data) > 4000:
        return None
    peaks: list[float] = []
    for value in data:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        peaks.append(round(min(1.0, max(0.0, float(value))), 4))
    return peaks or None


# --------------------------------------------------------------------------
# Transcription worker — runs in the background after the upload response
# --------------------------------------------------------------------------
async def run_transcription(project_id: str, audio_path: str | None = None) -> None:
    service = get_transcription_service()
    if service is None:
        await _update(project_id, transcription=TranscriptionInfo(status="unavailable", completed_at=utcnow()))
        return

    tmp_path = audio_path if audio_path and os.path.exists(audio_path) else None
    try:
        if tmp_path is None:
            # re-runs (POST /analyze) fetch the audio back from R2
            doc = await db.projects.find_one({"id": project_id})
            if not doc:
                return
            object_key = doc["audio"]["object_key"]
            suffix = Path(doc["audio"]["file_name"]).suffix or ".bin"
            tmp_path = await get_storage().download_to_temp(object_key, suffix=suffix)

        await _update(project_id, transcription=TranscriptionInfo(status="processing"))
        result = await service.transcribe(tmp_path)

        docs = [
            TranscriptSegment(
                project_id=project_id,
                index=index,
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                text=segment.text,
            ).model_dump()
            for index, segment in enumerate(result.segments)
        ]
        await db.transcript_segments.delete_many({"project_id": project_id})
        if docs:
            await db.transcript_segments.insert_many(docs)

        await _update(
            project_id,
            transcription=TranscriptionInfo(
                status="ready",
                segment_count=len(docs),
                language=result.language,
                model=service.model_name,
                completed_at=utcnow(),
            ),
        )
    except AudioTooLargeForTranscription as exc:
        await _update(project_id, transcription=TranscriptionInfo(status="failed", error=str(exc), completed_at=utcnow()))
    except Exception as exc:
        logger.exception("transcription failed for project %s", project_id)
        await _update(
            project_id,
            transcription=TranscriptionInfo(status="failed", error=str(exc)[:500], completed_at=utcnow()),
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@router.post("/projects", response_model=Project, status_code=201)
async def create_project(
    background: BackgroundTasks,
    file: UploadFile,
    title: Annotated[str, Form()] = "",
    peaks: Annotated[str, Form()] = "",
    client_duration: Annotated[float | None, Form()] = None,
) -> Project:
    storage = get_storage()  # raises StorageNotConfigured -> 503 via the global handler

    original_name = file.filename or "audio"
    if not is_allowed_upload(original_name, file.content_type):
        raise HTTPException(
            status_code=415,
            detail="unsupported file — upload an audio file (mp3, wav, m4a, mp4, aac, ogg, opus, flac, webm)",
        )

    limit = max_upload_bytes()
    suffix = Path(original_name).suffix.lower()
    fd, tmp_path = tempfile.mkstemp(prefix="chronicle-upload-", suffix=suffix)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await file.read(_READ_CHUNK):
                size += len(chunk)
                if size > limit:
                    raise _UploadTooLarge()
                out.write(chunk)
    except _UploadTooLarge:
        os.unlink(tmp_path)
        raise HTTPException(
            status_code=413,
            detail=f"audio exceeds the {limit // (1024 * 1024)} MB upload limit",
        )
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    try:
        # Real server-side measurement of the actual file
        duration = probe_duration(tmp_path)
        if duration is None and client_duration is not None and client_duration > 0:
            # fallback: duration measured by the browser's own decoder
            duration = round(client_duration, 3)

        project_id = str(uuid.uuid4())
        safe_name = sanitize_filename(original_name)
        object_key = f"audio/{project_id}/{safe_name}"
        content_type = guess_content_type(original_name, file.content_type)

        try:
            await storage.upload_file(tmp_path, object_key, content_type)
        except StorageNotConfigured:
            raise
        except Exception as exc:
            logger.exception("R2 upload failed for %s", object_key)
            raise HTTPException(status_code=502, detail=f"object storage upload failed: {exc}") from exc

        scheduled = get_transcription_service() is not None
        project = Project(
            id=project_id,
            title=(title.strip() or Path(original_name).stem)[:120] or "Untitled narration",
            status="ready",
            audio=AudioAsset(
                object_key=object_key,
                file_name=safe_name,
                content_type=content_type,
                size_bytes=size,
                duration_seconds=duration,
                waveform=_parse_peaks(peaks),
            ),
            transcription=TranscriptionInfo(status="pending" if scheduled else "unavailable"),
        )
        await db.projects.insert_one(project.model_dump())

        if scheduled:
            # ownership of the temp file moves to the transcription worker
            background.add_task(run_transcription, project_id, tmp_path)
        return project
    except HTTPException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects() -> list[ProjectSummary]:
    docs = await db.projects.find().sort("created_at", -1).to_list(500)
    return [ProjectSummary.from_project(Project(**doc)) for doc in docs]


@router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str) -> Project:
    return await project_or_404(project_id)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict:
    project = await project_or_404(project_id)
    try:
        await get_storage().delete(project.audio.object_key)
    except StorageNotConfigured:
        raise
    except Exception as exc:
        # storage delete is best-effort; the DB records still go away
        logger.warning("could not delete %s from storage: %s", project.audio.object_key, exc)
    await db.projects.delete_one({"id": project_id})
    await db.transcript_segments.delete_many({"project_id": project_id})
    await db.scenes.delete_many({"project_id": project_id})
    await db.render_jobs.delete_many({"project_id": project_id})
    return {"ok": True, "id": project_id}


@router.post("/projects/{project_id}/analyze", response_model=Project)
async def analyze_project(project_id: str, background: BackgroundTasks) -> Project:
    project = await project_or_404(project_id)
    if get_transcription_service() is None:
        raise HTTPException(
            status_code=503,
            detail="Transcription is not configured — set EMERGENT_LLM_KEY in backend/.env",
        )
    if project.transcription.status == "processing":
        raise HTTPException(status_code=409, detail="Transcription is already in progress")

    try:
        await get_storage().head(project.audio.object_key)
    except Exception as exc:
        raise HTTPException(status_code=410, detail="the audio object no longer exists in storage") from exc

    await _update(project_id, transcription=TranscriptionInfo(status="processing", error=None))
    background.add_task(run_transcription, project_id)  # no local file: downloads from R2
    project.transcription = TranscriptionInfo(status="processing")
    return project


@router.get("/projects/{project_id}/audio")
async def stream_audio(project_id: str, request: Request):
    """Range-aware audio stream — powers the editor's <audio> element through /api."""
    project = await project_or_404(project_id)
    storage = get_storage()
    key = project.audio.object_key

    try:
        head = await storage.head(key)
    except ClientError as exc:
        raise HTTPException(status_code=410, detail="the audio object no longer exists in storage") from exc
    total = int(head["ContentLength"])
    content_type = head.get("ContentType") or project.audio.content_type

    range_header = request.headers.get("range")
    match = None
    if range_header:
        match = _parse_range(range_header)

    if match is not None:
        start, end_requested = match
        if start >= total:
            return StreamingResponse(
                status_code=416,
                headers={"content-range": f"bytes */{total}"},
            )
        end = total - 1 if end_requested is None else min(end_requested, total - 1)
        obj = await storage.get(key, range_header=f"bytes={start}-{end}")
        length = end - start + 1
        return StreamingResponse(
            iter_body(obj["Body"]),
            status_code=206,
            media_type=content_type,
            headers={
                "accept-ranges": "bytes",
                "content-range": f"bytes {start}-{end}/{total}",
                "content-length": str(length),
            },
        )

    obj = await storage.get(key)
    return StreamingResponse(
        iter_body(obj["Body"]),
        status_code=200,
        media_type=content_type,
        headers={"accept-ranges": "bytes", "content-length": str(total)},
    )


def _parse_range(value: str) -> tuple[int, int | None] | None:
    match = _RANGE_PATTERN.fullmatch(value.strip())
    if not match:
        return None
    start_raw, end_raw = match.group(1), match.group(2)
    if start_raw == "":
        return None  # suffix ranges not needed for stage 1 — serve the full body
    return int(start_raw), int(end_raw) if end_raw else None


import re  # noqa: E402  (kept beside its only consumer for readability)

_RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)")
