"""AI scene-planning seam (stage 2).

Contract: given the project and its transcript segments, produce an ordered list of
Scene objects that tile the narration — each with a SceneTreatment (Ken Burns archival
photo, map, chart, motion typography, stock footage, title card), a creative brief and
an asset plan. Stage 1 stores the contract and exposes the seam; no planner is
implemented yet, and nothing pretends otherwise.
"""

from typing import Protocol

from lib.errors import FeatureDisabled
from models.projects import Project
from models.timeline import Scene, TranscriptSegment


class ScenePlanner(Protocol):
    async def plan(self, project: Project, segments: list[TranscriptSegment]) -> list[Scene]: ...


class DisabledScenePlanner:
    async def plan(self, project: Project, segments: list[TranscriptSegment]) -> list[Scene]:
        raise FeatureDisabled("AI scene planning", stage=2, reason="no planner implemented in stage 1")


def get_scene_planner() -> ScenePlanner:
    return DisabledScenePlanner()
