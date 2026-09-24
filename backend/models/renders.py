"""Render job contracts — the shape the stage-2 render pipeline will fulfil.

Mirror (hand-written) in frontend/src/lib/types.ts — keep the pair in sync.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from models.projects import as_utc, utcnow


class RenderOutput(BaseModel):
    object_key: str
    size_bytes: int
    duration_seconds: float | None = None


class RenderJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    status: Literal["queued", "running", "succeeded", "failed"] = "queued"
    progress: float = 0.0
    output: RenderOutput | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return as_utc(value) or value
