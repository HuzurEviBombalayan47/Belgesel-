"""Timeline APIs: transcript segments and AI-planned visual scenes.

The scene-planning pass runs as a background task (a long transcript means many AI
calls), so the request returns immediately and the editor polls
`project.scene_planning` for honest progress. A failed AI call is recorded as a real
error — no placeholder scenes are ever written.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pymongo import ASCENDING

from lib.db import db
from lib.errors import ScenePlanningError
from models.projects import Project, ScenePlanningInfo, utcnow
from models.timeline import Scene, TranscriptSegment
from routers.projects import project_or_404
from services.scene_planner import get_scene_planner

logger = logging.getLogger(__name__)
router = APIRouter()


async def _set_planning(project_id: str, info: ScenePlanningInfo) -> None:
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"scene_planning": info.model_dump(), "updated_at": utcnow()}},
    )


async def load_segments(project_id: str) -> list[TranscriptSegment]:
    docs = (
        await db.transcript_segments.find({"project_id": project_id})
        .sort([("start_seconds", ASCENDING), ("index", ASCENDING)])
        .to_list(5000)
    )
    return [TranscriptSegment(**doc) for doc in docs]


async def run_scene_planning(project_id: str) -> None:
    """Background worker: transcript -> AI scene plans -> scenes collection."""
    planner = get_scene_planner()
    project_doc = await db.projects.find_one({"id": project_id})
    if not project_doc or planner is None:
        return
    project = Project(**project_doc)
    segments = await load_segments(project_id)

    await _set_planning(
        project_id,
        ScenePlanningInfo(
            status="processing",
            model=planner.model_name,
            segments_total=len(segments),
        ),
    )

    try:
        scenes = await planner.plan(project, segments)
        await db.scenes.delete_many({"project_id": project_id})
        if scenes:
            await db.scenes.insert_many([scene.model_dump() for scene in scenes])
        await _set_planning(
            project_id,
            ScenePlanningInfo(
                status="ready",
                scene_count=len(scenes),
                model=planner.model_name,
                segments_planned=len(segments),
                segments_total=len(segments),
                completed_at=utcnow(),
            ),
        )
    except ScenePlanningError as exc:
        logger.error("scene planning failed for %s: %s", project_id, exc)
        await _set_planning(
            project_id,
            ScenePlanningInfo(
                status="failed",
                error=str(exc)[:600],
                model=planner.model_name,
                segments_total=len(segments),
                completed_at=utcnow(),
            ),
        )
    except Exception as exc:
        logger.exception("scene planning crashed for %s", project_id)
        await _set_planning(
            project_id,
            ScenePlanningInfo(
                status="failed",
                error=f"unexpected planner error: {exc}"[:600],
                model=planner.model_name,
                segments_total=len(segments),
                completed_at=utcnow(),
            ),
        )


@router.get("/projects/{project_id}/transcript", response_model=list[TranscriptSegment])
async def get_transcript(project_id: str) -> list[TranscriptSegment]:
    await project_or_404(project_id)
    return await load_segments(project_id)


@router.get("/projects/{project_id}/scenes", response_model=list[Scene])
async def get_scenes(project_id: str) -> list[Scene]:
    await project_or_404(project_id)
    docs = (
        await db.scenes.find({"project_id": project_id})
        .sort([("start_time", ASCENDING), ("index", ASCENDING)])
        .to_list(5000)
    )
    return [Scene(**doc) for doc in docs]


@router.post("/projects/{project_id}/scenes/plan", response_model=Project, status_code=202)
async def plan_scenes(project_id: str, background: BackgroundTasks) -> Project:
    """"Analyze & Create Scenes" — kicks off the real AI planning pass."""
    project = await project_or_404(project_id)

    planner = get_scene_planner()
    if planner is None:
        raise HTTPException(
            status_code=424,
            detail="The AI scene planner is not configured — set EMERGENT_LLM_KEY in backend/.env",
        )
    if project.transcription.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=(
                "The transcript is not ready yet — scenes are planned from the timestamped "
                f"transcript (transcription is currently '{project.transcription.status}')"
            ),
        )
    if project.scene_planning.status == "processing":
        raise HTTPException(status_code=409, detail="Scene planning is already in progress")

    segments = await load_segments(project_id)
    if not segments:
        raise HTTPException(
            status_code=409, detail="There are no transcript segments to analyse"
        )

    info = ScenePlanningInfo(
        status="queued", model=planner.model_name, segments_total=len(segments)
    )
    await _set_planning(project_id, info)
    background.add_task(run_scene_planning, project_id)
    project.scene_planning = info
    return project


@router.delete("/projects/{project_id}/scenes")
async def clear_scenes(project_id: str) -> dict:
    """Discard the current plan so the user can re-run the planner from scratch."""
    await project_or_404(project_id)
    result = await db.scenes.delete_many({"project_id": project_id})
    await _set_planning(project_id, ScenePlanningInfo(status="idle"))
    return {"ok": True, "deleted": result.deleted_count}
