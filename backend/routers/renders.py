"""Render job seam.

Stage 1 exposes the job API shape and wires submission to the (disabled) render
engine: POST answers an honest 501 via the FeatureDisabled handler — it never
pretends a render succeeded. GET lists whatever jobs exist (empty today; the
stage-2 pipeline appends here).
"""

from fastapi import APIRouter

from lib.db import db
from models.renders import RenderJob
from rendering.pipeline import get_render_engine
from routers.projects import project_or_404

router = APIRouter()


@router.post("/projects/{project_id}/renders", response_model=RenderJob, status_code=202)
async def create_render(project_id: str) -> RenderJob:
    project = await project_or_404(project_id)
    engine = get_render_engine()
    return await engine.submit(project)


@router.get("/projects/{project_id}/renders", response_model=list[RenderJob])
async def list_renders(project_id: str) -> list[RenderJob]:
    await project_or_404(project_id)
    docs = await db.render_jobs.find({"project_id": project_id}).to_list(200)
    return [RenderJob(**doc) for doc in docs]
