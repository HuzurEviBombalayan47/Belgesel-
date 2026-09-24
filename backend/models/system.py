"""Runtime capability status — the UI reads this to render honest setup states."""

from pydantic import BaseModel


class StorageStatus(BaseModel):
    provider: str = "cloudflare_r2"
    configured: bool
    bucket: str | None = None


class TranscriptionStatus(BaseModel):
    configured: bool
    model: str | None = None


class ScenePlanningStatus(BaseModel):
    configured: bool
    model: str | None = None


class SystemStatus(BaseModel):
    app: str = "Chronicle AI"
    version: str = "0.2.0"
    storage: StorageStatus
    transcription: TranscriptionStatus
    scene_planning: ScenePlanningStatus
    rendering: dict = {"enabled": False, "stage": 3}
    max_upload_bytes: int
