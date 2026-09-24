"""Runtime capability status — the UI reads this to render honest setup states
(storage configured or not, transcription available, upload limits)."""

from fastapi import APIRouter

from lib.media import max_upload_bytes
from lib.storage import get_storage, storage_configured
from models.system import StorageStatus, SystemStatus, TranscriptionStatus
from services.transcription import get_transcription_service

router = APIRouter()


@router.get("/system/status", response_model=SystemStatus)
async def system_status() -> SystemStatus:
    configured = storage_configured()
    bucket = get_storage().bucket if configured else None
    service = get_transcription_service()
    return SystemStatus(
        storage=StorageStatus(configured=configured, bucket=bucket),
        transcription=TranscriptionStatus(
            configured=service is not None, model=service.model_name if service else None
        ),
        max_upload_bytes=max_upload_bytes(),
    )
