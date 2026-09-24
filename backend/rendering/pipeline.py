"""Timeline-based rendering seam (stage 2+).

The rendering system is deliberately modular — visual generation logic is NOT
hard-coded anywhere in stage 1. A RenderEngine consumes a project and its timeline
(transcript segments + planned scenes) and drives a RenderJob through
queued -> running -> succeeded/failed, storing its output via the R2 storage layer.

Stage-2 extensions that build on this seam (without rebuilding anything):
- compositor: layered rendering driven by SceneTreatment — Ken Burns image moves,
  maps, charts, kinetic typography, transitions, synchronized SFX (ffmpeg/MoviePy
  or a headless-browser frame pipeline behind the same interface).
- asset resolution: scenes reference asset_ids resolved through services/storage
  (asset-handling is its own layer, separate from rendering).
- profiles: multiple engines (720p preview / 1080p final) can register by profile.

Stage 1 registers only the disabled engine: the API surface exists and answers an
honest 501 instead of pretending to render.
"""

from typing import Protocol

from lib.errors import FeatureDisabled
from models.projects import Project
from models.renders import RenderJob


class RenderEngine(Protocol):
    async def submit(self, project: Project, profile: str = "preview") -> RenderJob: ...


class DisabledRenderEngine:
    async def submit(self, project: Project, profile: str = "preview") -> RenderJob:
        raise FeatureDisabled(
            "Video rendering", stage=2, reason="the compositor is not implemented in stage 1"
        )


def get_render_engine() -> RenderEngine:
    return DisabledRenderEngine()
