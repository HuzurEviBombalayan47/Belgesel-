"""Runtime capability status — the UI reads this to render honest setup states
(storage configured or not, transcription available, AI planner available)."""

from fastapi import APIRouter

from lib.media import max_upload_bytes
from lib.storage import get_storage, storage_configured
from models.system import (
    ScenePlanningStatus,
    StorageStatus,
    SystemStatus,
    TranscriptionStatus,
)
from services.scene_planner import get_scene_planner
from services.transcription import get_transcription_service

router = APIRouter()


@router.get("/system/status", response_model=SystemStatus)
async def system_status() -> SystemStatus:
    configured = storage_configured()
    bucket = get_storage().bucket if configured else None
    stt = get_transcription_service()
    planner = get_scene_planner()
    return SystemStatus(
        storage=StorageStatus(configured=configured, bucket=bucket),
        transcription=TranscriptionStatus(
            configured=stt is not None, model=stt.model_name if stt else None
        ),
        scene_planning=ScenePlanningStatus(
            configured=planner is not None, model=planner.model_name if planner else None
        ),
        max_upload_bytes=max_upload_bytes(),
    )
