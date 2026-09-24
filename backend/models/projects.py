"""Pydantic contracts for projects + audio assets.

Mirror (hand-written) in frontend/src/lib/types.ts — keep the pair in sync.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Motor hands naive datetimes back from BSON — normalise to aware UTC so
    Pydantic serialises with an offset and JavaScript `new Date(...)` parses right."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class AudioAsset(BaseModel):
    object_key: str
    file_name: str
    content_type: str
    size_bytes: int
    duration_seconds: float | None = None
    # Normalized 0..1 peak envelope of the actual audio (computed from the decoded
    # samples), oldest sample first. None when the client could not decode.
    waveform: list[float] | None = None


class TranscriptionInfo(BaseModel):
    status: Literal["pending", "processing", "ready", "failed", "unavailable"] = "pending"
    error: str | None = None
    segment_count: int = 0
    language: str | None = None
    model: str | None = None
    completed_at: datetime | None = None

    @field_validator("completed_at", mode="after")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        return as_utc(value)


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    status: Literal["ready", "failed"] = "ready"
    audio: AudioAsset
    transcription: TranscriptionInfo = Field(default_factory=TranscriptionInfo)
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return as_utc(value) or value


class ProjectSummary(BaseModel):
    id: str
    title: str
    status: str
    file_name: str
    content_type: str
    size_bytes: int
    duration_seconds: float | None
    transcription_status: str
    segment_count: int
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return as_utc(value) or value

    @classmethod
    def from_project(cls, project: Project) -> "ProjectSummary":
        return cls(
            id=project.id,
            title=project.title,
            status=project.status,
            file_name=project.audio.file_name,
            content_type=project.audio.content_type,
            size_bytes=project.audio.size_bytes,
            duration_seconds=project.audio.duration_seconds,
            transcription_status=project.transcription.status,
            segment_count=project.transcription.segment_count,
            created_at=project.created_at,
        )
