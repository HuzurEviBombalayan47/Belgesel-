"""Timeline data contracts — transcript segments and AI-planned visual scenes.

These models are the shared language between speech analysis (Whisper), the AI scene
planner (Gemini) and the timeline renderer. Stage 3 will attach real assets to each
scene by resolving `visual_search_queries` — nothing here downloads or fabricates media.

Mirrored by hand in frontend/src/lib/types.ts — keep the pair in sync.
"""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from models.projects import as_utc, utcnow


class SceneType(str, Enum):
    """What kind of visual carries this moment of narration."""

    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    HISTORICAL_IMAGE = "HISTORICAL_IMAGE"
    DOCUMENT = "DOCUMENT"
    MAP = "MAP"
    CHART = "CHART"
    TEXT_ANIMATION = "TEXT_ANIMATION"
    MOTION_GRAPHIC = "MOTION_GRAPHIC"
    LOGO = "LOGO"
    SCREENSHOT = "SCREENSHOT"
    MIXED = "MIXED"


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
    """One planned visual beat of the documentary.

    `start_time` / `end_time` are seconds on the audio timeline. The remaining fields
    are the structured visual plan the renderer and the asset resolver consume.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    index: int

    # --- timing ---
    start_time: float
    end_time: float

    # --- what is being said ---
    transcript_text: str

    # --- the AI's visual plan ---
    scene_type: SceneType
    visual_goal: str
    visual_search_queries: list[str] = Field(default_factory=list)
    suggested_visual_treatment: str
    important_text: list[str] = Field(default_factory=list)
    animation_type: str
    transition_type: str
    sound_effect_suggestion: str | None = None

    # --- stage-3 asset binding (kept empty here; no assets are fetched yet) ---
    status: str = "planned"
    asset_ids: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=utcnow)

    @field_validator("created_at", mode="after")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return as_utc(value) or value

    @property
    def duration(self) -> float:
        return round(self.end_time - self.start_time, 3)
