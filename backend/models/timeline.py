"""Timeline data contracts — transcript segments and visual scenes.

These models are the shared language between speech analysis (Whisper worker),
the AI scene planner (stage 2) and the timeline renderer. The editor reads them
over /api today; stage 2 writes the same rows.
"""

import uuid
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from models.projects import as_utc, utcnow
from datetime import datetime


class SceneTreatment(str, Enum):
    """The documentary visual treatments the scene planner will assign (stage 2)."""

    KEN_BURNS = "ken_burns"  # animated photographs, cinematic image movement
    ARCHIVAL_PHOTO = "archival_photo"  # historical photographs
    MAP = "map"  # cartographic sequences
    CHART = "chart"  # documentary graphics / data
    MOTION_TYPOGRAPHY = "motion_typography"  # emphasized words and numbers
    STOCK_FOOTAGE = "stock_footage"  # internet-sourced images / stock footage
    TITLE_CARD = "title_card"


class TranscriptSegment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    index: int
    start_seconds: float
    end_seconds: float
    text: str
    speaker: str | None = None
    confidence: float | None = None


class Scene(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    index: int
    start_seconds: float
    end_seconds: float
    title: str | None = None
    treatment: SceneTreatment | None = None
    # Scene-planner intent: feeds asset search and the render compositor (stage 2).
    brief: str | None = None
    status: Literal["planned", "awaiting_assets", "ready"] = "planned"
    asset_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
