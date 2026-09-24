"""Read APIs for the editor timeline: transcript segments and visual scenes.

Stage 2 writes the rows (the Whisper worker writes segments; the AI scene planner
writes scenes) — the editor renders whatever exists today with honest empty states.
"""

from fastapi import APIRouter
from pymongo import ASCENDING

from lib.db import db
from models.timeline import Scene, TranscriptSegment
from routers.projects import project_or_404

router = APIRouter()


@router.get("/projects/{project_id}/transcript", response_model=list[TranscriptSegment])
async def get_transcript(project_id: str) -> list[TranscriptSegment]:
    await project_or_404(project_id)
    docs = (
        await db.transcript_segments.find({"project_id": project_id})
        .sort([("start_seconds", ASCENDING), ("index", ASCENDING)])
        .to_list(5000)
    )
    return [TranscriptSegment(**doc) for doc in docs]


@router.get("/projects/{project_id}/scenes", response_model=list[Scene])
async def get_scenes(project_id: str) -> list[Scene]:
    await project_or_404(project_id)
    docs = (
        await db.scenes.find({"project_id": project_id})
        .sort([("start_seconds", ASCENDING), ("index", ASCENDING)])
        .to_list(5000)
    )
    return [Scene(**doc) for doc in docs]
