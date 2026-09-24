"""AI Scene Planner — real Gemini call that turns a timestamped transcript into
structured documentary scene plans.

Design notes
- The planner is a seam (`ScenePlanner` Protocol): the router depends on the interface,
  so stage 3 can add asset resolution or swap models without touching the API layer.
- Long transcripts are planned in windows of consecutive segments so quality stays high
  and each response stays small enough to parse reliably. Windows are planned with
  bounded concurrency and merged in order.
- Output is validated against the Pydantic `Scene` model. A malformed or empty AI
  response raises ScenePlanningError — no placeholder or fabricated scenes, ever.
- Nothing here downloads assets or renders video; it only produces the plan.
"""

import asyncio
import json
import logging
import os
import re
from typing import Protocol

from lib.errors import ScenePlanningError
from models.projects import Project
from models.timeline import Scene, SceneType, TranscriptSegment

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-2.5-flash"

# Segments per AI request. Small enough that the model reasons carefully about each
# beat and the JSON stays parseable; large enough to see narrative context.
WINDOW_SIZE = 18
MAX_CONCURRENCY = 3

SCENE_TYPES = [t.value for t in SceneType]

ANIMATION_HINTS = [
    "KEN_BURNS_ZOOM_IN", "KEN_BURNS_ZOOM_OUT", "SLOW_PAN_LEFT", "SLOW_PAN_RIGHT",
    "PARALLAX_2_5D", "STATIC_HOLD", "NUMBER_COUNT_UP", "TYPE_ON", "WORD_POP",
    "LINE_DRAW", "MAP_ROUTE_REVEAL", "BAR_GROW", "SCALE_POP", "SLOW_PUSH_IN",
]
TRANSITION_HINTS = [
    "CUT", "CROSSFADE", "DIP_TO_BLACK", "WHIP_PAN", "FILM_BURN", "PAPER_SLIDE",
    "GLITCH", "LIGHT_LEAK", "MATCH_CUT",
]

SYSTEM_MESSAGE = """You are the visual director of a high-end YouTube documentary channel \
(in the register of Vox, Johnny Harris, Fern or Neo). You receive a timestamped transcript \
of a narration and you decide, beat by beat, what the viewer should SEE.

You think like an editor, not like a stock-footage search box:
- Group consecutive transcript segments into meaningful visual scenes. A scene usually \
spans 3-12 seconds; one sentence may be one scene, and a continuing thought may share a scene.
- Choose the scene_type that genuinely serves the MEANING of the words. A date or a company's \
past -> HISTORICAL_IMAGE; a person -> PHOTO; money, quantities, growth or comparison -> CHART \
or TEXT_ANIMATION; a place, route or territory -> MAP; a filing, letter, report or headline -> \
DOCUMENT; a product UI or website -> SCREENSHOT; a brand mark -> LOGO; an abstract idea with no \
literal referent -> MOTION_GRAPHIC or TEXT_ANIMATION; motion/event footage -> VIDEO; MIXED only \
when a scene truly layers two kinds of visual.
- NEVER force a visual where none makes sense. When the narration is abstract, transitional or \
purely rhetorical, prefer TEXT_ANIMATION or MOTION_GRAPHIC built from the narration's own words \
instead of inventing an unrelated image.
- visual_search_queries must be concrete, searchable and derived from the ACTUAL subject: real \
names, places, organisations, objects, years, events. 1-3 queries per scene.
  GOOD: "Steve Jobs 1997 Macworld keynote", "Apple Computer 1997 annual report cover", \
"Cupertino Infinite Loop campus aerial 1990s"
  FORBIDDEN (never output these or anything like them): "cinematic background", \
"business background", "dark cinematic video", "abstract technology", "corporate b-roll", \
"motivational footage", "generic office".
  For CHART, TEXT_ANIMATION and MOTION_GRAPHIC scenes, queries may be an empty list because the \
visual is generated, not searched.
- important_text: the exact words, numbers, dates or names from THIS scene's narration that \
deserve on-screen emphasis (e.g. "1997", "$1 billion", "Steve Jobs"). Empty list when nothing \
deserves emphasis. Never invent facts that are not in the narration.
- animation_type and transition_type must suit the content: a solemn archival photo does not \
get a whip pan; a punchy number can pop or count up.
- sound_effect_suggestion: a short, specific cue ("camera shutter click", "paper rustle", \
"low cinematic riser", "typewriter keystrokes") or null when silence serves better.

The narration may be in any language. Write visual_goal, suggested_visual_treatment, \
animation_type and transition_type in English, and write visual_search_queries in English so \
they work against image and footage libraries — but keep transcript_text and important_text \
verbatim in the narration's own language. Translate proper nouns faithfully (a Turkish \
narration about "oyun stüdyoları" yields queries like "video game studio office crunch").

Return ONLY a JSON object of the form {"scenes": [ ... ]}. No markdown, no commentary."""

USER_TEMPLATE = """Project title: {title}

Plan the visual scenes for the transcript window below. Cover the narration from \
{window_start:.2f}s to {window_end:.2f}s. Scene times must stay inside that range, must be in \
chronological order and must not overlap. Do not leave meaningful narration uncovered.

Each scene object must contain exactly these keys:
  "start_time": number (seconds)
  "end_time": number (seconds)
  "transcript_text": string  (the narration this scene covers, copied from the transcript)
  "scene_type": one of {scene_types}
  "visual_goal": string  (one sentence: what this shot must communicate)
  "visual_search_queries": array of strings  (concrete, subject-derived; [] for generated visuals)
  "suggested_visual_treatment": string  (grade/framing/texture, e.g. "desaturated archival grade, \
slight film grain, 4:3 photo floated on dark canvas")
  "important_text": array of strings  (exact words/numbers to emphasise; [] if none)
  "animation_type": string  (e.g. one of {animations})
  "transition_type": string  (e.g. one of {transitions})
  "sound_effect_suggestion": string or null

Transcript window:
{transcript}

Return only {{"scenes": [...]}}."""


class ScenePlanner(Protocol):
    model_name: str

    async def plan(self, project: Project, segments: list[TranscriptSegment]) -> list[Scene]: ...


def _extract_json(raw: str) -> dict:
    """Pull the JSON object out of a model response, tolerating code fences."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _clean_queries(value: object) -> list[str]:
    """Drop the generic filler the prompt forbids, keep concrete subject queries."""
    banned = (
        "cinematic background", "business background", "dark cinematic", "abstract technology",
        "corporate b-roll", "corporate broll", "motivational footage", "generic office",
        "stock footage", "background video", "b-roll footage",
    )
    out: list[str] = []
    items = value if isinstance(value, list) else []
    for item in items:
        query = str(item).strip()
        if not query or len(query) < 3:
            continue
        lowered = query.lower()
        if any(phrase in lowered for phrase in banned):
            continue
        if query not in out:
            out.append(query)
    return out[:3]


def _clean_text_list(value: object) -> list[str]:
    out: list[str] = []
    items = value if isinstance(value, list) else []
    for item in items:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out[:6]


def _normalise_token(value: object, fallback: str) -> str:
    token = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    return re.sub(r"[^A-Z0-9_]", "", token) or fallback


def describe_ai_error(exc: BaseException) -> str:
    """Translate provider failures into something the user can act on."""
    text = str(exc)
    lowered = text.lower()
    if "budget has been exceeded" in lowered or "budget_exceeded" in lowered:
        return (
            "the AI key's budget is exhausted — top up your Emergent credits, or add your own "
            "GEMINI_API_KEY to backend/.env to use Google directly"
        )
    if "rate limit" in lowered or "429" in lowered:
        return "the AI provider is rate limiting the request — retry in a moment"
    if "unauthorized" in lowered or "api key" in lowered or "401" in lowered:
        return "the AI key was rejected — check GEMINI_API_KEY / EMERGENT_LLM_KEY in backend/.env"
    if "timed out" in lowered or "timeout" in lowered:
        return "the AI request timed out"
    return text


class GeminiScenePlanner:
    """Real AI planner. Uses the user's own GEMINI_API_KEY when present, otherwise the
    Emergent universal key. Keys live only in backend env — never sent to the frontend."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, provider: str = DEFAULT_PROVIDER):
        self._api_key = api_key
        self._provider = provider
        self.model_name = model

    async def plan(self, project: Project, segments: list[TranscriptSegment]) -> list[Scene]:
        if not segments:
            raise ScenePlanningError(
                "there is no transcript to analyse — run the transcription first"
            )

        windows = [segments[i : i + WINDOW_SIZE] for i in range(0, len(segments), WINDOW_SIZE)]
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def run(window: list[TranscriptSegment]) -> list[dict]:
            async with semaphore:
                return await self._plan_window(project, window)

        results = await asyncio.gather(
            *(run(window) for window in windows), return_exceptions=True
        )

        raw_scenes: list[dict] = []
        failures: list[str] = []
        for index, result in enumerate(results):
            if isinstance(result, BaseException):
                failures.append(f"window {index + 1}: {result}")
                continue
            raw_scenes.extend(result)

        if not raw_scenes:
            detail = "; ".join(failures[:3]) if failures else "the model returned no scenes"
            raise ScenePlanningError(f"the AI scene planner produced no usable scenes — {detail}")

        if failures:
            # Partial coverage is reported honestly by the caller rather than silently padded.
            logger.warning("scene planning had %d failed window(s): %s", len(failures), failures[:3])

        return self._finalise(project, raw_scenes, segments, failures)

    async def _plan_window(self, project: Project, window: list[TranscriptSegment]) -> list[dict]:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        window_start = window[0].start_seconds
        window_end = window[-1].end_seconds
        transcript = "\n".join(
            f"[{segment.start_seconds:.2f} - {segment.end_seconds:.2f}] {segment.text}"
            for segment in window
        )
        prompt = USER_TEMPLATE.format(
            title=project.title,
            window_start=window_start,
            window_end=window_end,
            scene_types=", ".join(SCENE_TYPES),
            animations=", ".join(ANIMATION_HINTS),
            transitions=", ".join(TRANSITION_HINTS),
            transcript=transcript,
        )

        chat = LlmChat(
            api_key=self._api_key,
            session_id=f"scene-plan-{project.id}-{int(window_start * 1000)}",
            system_message=SYSTEM_MESSAGE,
        ).with_model(self._provider, self.model_name)

        try:
            response = await asyncio.wait_for(
                chat.send_message(UserMessage(text=prompt)), timeout=180
            )
        except asyncio.TimeoutError as exc:
            raise ScenePlanningError("the AI request timed out after 180s") from exc
        except Exception as exc:
            raise ScenePlanningError(f"the AI request failed — {describe_ai_error(exc)}") from exc

        text = response if isinstance(response, str) else str(response)
        try:
            payload = _extract_json(text)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ScenePlanningError(
                f"the AI returned a response that is not valid JSON: {text[:180]}"
            ) from exc

        scenes = payload.get("scenes") if isinstance(payload, dict) else None
        if not isinstance(scenes, list) or not scenes:
            raise ScenePlanningError("the AI response contained no 'scenes' array")

        cleaned: list[dict] = []
        for item in scenes:
            if not isinstance(item, dict):
                continue
            try:
                start = float(item.get("start_time"))
                end = float(item.get("end_time"))
            except (TypeError, ValueError):
                continue
            # keep the AI inside the window it was asked to cover
            start = max(window_start, min(start, window_end))
            end = max(start, min(end, window_end))
            if end - start < 0.2:
                continue
            item["start_time"], item["end_time"] = round(start, 3), round(end, 3)
            cleaned.append(item)

        if not cleaned:
            raise ScenePlanningError("the AI returned scenes with unusable timings")
        return cleaned

    def _finalise(
        self,
        project: Project,
        raw_scenes: list[dict],
        segments: list[TranscriptSegment],
        failures: list[str],
    ) -> list[Scene]:
        raw_scenes.sort(key=lambda item: item["start_time"])

        scenes: list[Scene] = []
        previous_end = 0.0
        for item in raw_scenes:
            start = max(float(item["start_time"]), previous_end)  # de-overlap
            end = float(item["end_time"])
            if end - start < 0.2:
                continue

            scene_type = str(item.get("scene_type", "")).strip().upper()
            if scene_type not in SCENE_TYPES:
                scene_type = SceneType.MIXED.value

            text = str(item.get("transcript_text", "") or "").strip()
            if not text:
                text = " ".join(
                    segment.text
                    for segment in segments
                    if segment.start_seconds < end and segment.end_seconds > start
                ).strip()

            goal = str(item.get("visual_goal", "") or "").strip()
            treatment = str(item.get("suggested_visual_treatment", "") or "").strip()
            if not goal or not treatment:
                # a scene without a plan is not a scene — drop it rather than pad it
                continue

            sfx = item.get("sound_effect_suggestion")
            sfx_text = str(sfx).strip() if sfx not in (None, "", "null") else None

            try:
                scenes.append(
                    Scene(
                        project_id=project.id,
                        index=len(scenes),
                        start_time=round(start, 3),
                        end_time=round(end, 3),
                        transcript_text=text,
                        scene_type=SceneType(scene_type),
                        visual_goal=goal,
                        visual_search_queries=_clean_queries(item.get("visual_search_queries")),
                        suggested_visual_treatment=treatment,
                        important_text=_clean_text_list(item.get("important_text")),
                        animation_type=_normalise_token(item.get("animation_type"), "STATIC_HOLD"),
                        transition_type=_normalise_token(item.get("transition_type"), "CUT"),
                        sound_effect_suggestion=sfx_text,
                    )
                )
            except Exception as exc:  # pydantic validation
                logger.warning("dropping invalid scene from AI response: %s", exc)
                continue
            previous_end = scenes[-1].end_time

        if not scenes:
            raise ScenePlanningError(
                "every scene in the AI response failed validation — no scenes were created"
            )
        return scenes


_planner: ScenePlanner | None = None
_resolved = False


def get_scene_planner() -> ScenePlanner | None:
    """The configured planner, or None when no AI key is available.

    Key precedence: the user's own GEMINI_API_KEY (talks to Google directly) wins over
    the Emergent universal key. Both are read from backend env only.
    """
    global _planner, _resolved
    if not _resolved:
        _resolved = True
        own_key = os.environ.get("GEMINI_API_KEY", "").strip()
        universal_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
        api_key = own_key or universal_key
        if api_key:
            _planner = GeminiScenePlanner(
                api_key=api_key,
                model=os.environ.get("SCENE_PLANNER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
                provider=os.environ.get("SCENE_PLANNER_PROVIDER", DEFAULT_PROVIDER).strip()
                or DEFAULT_PROVIDER,
            )
    return _planner


def scene_planning_configured() -> bool:
    return get_scene_planner() is not None
