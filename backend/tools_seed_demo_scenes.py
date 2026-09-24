"""VERIFICATION TOOL — not part of the application, never imported by the app.

Writes hand-authored Scene rows so the timeline lane, scene list and scene inspector
can be verified while the AI key is unavailable. These rows are NOT AI output and the
project they attach to is titled so that is unmistakable. Remove them with:

    python tools_seed_demo_scenes.py --clear <project_id>
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.timeline import Scene, SceneType  # noqa: E402

# Deliberately varied scene types so every badge/lane colour is exercised.
PLANS = [
    dict(
        start_time=0.0, end_time=3.2, scene_type=SceneType.HISTORICAL_IMAGE,
        transcript_text="Apple was nearly bankrupt in 1997.",
        visual_goal="Establish Apple at its lowest point with a period-accurate archival photograph.",
        visual_search_queries=["Apple Computer headquarters 1997", "Apple Cupertino campus 1990s"],
        suggested_visual_treatment="Desaturated archival grade, heavy film grain, 4:3 photo floated on dark canvas with soft vignette",
        important_text=["1997"], animation_type="KEN_BURNS_ZOOM_IN", transition_type="DIP_TO_BLACK",
        sound_effect_suggestion="low cinematic riser",
    ),
    dict(
        start_time=3.2, end_time=6.0, scene_type=SceneType.DOCUMENT,
        transcript_text="Its quarterly filings told the story in plain numbers.",
        visual_goal="Show the financial record itself so the claim feels documented, not asserted.",
        visual_search_queries=["Apple 1997 annual report cover", "SEC 10-K filing document scan"],
        suggested_visual_treatment="Paper-white scan on dark desk, slight keystone, highlighted line pulled forward",
        important_text=[], animation_type="SLOW_PUSH_IN", transition_type="PAPER_SLIDE",
        sound_effect_suggestion="paper rustle",
    ),
    dict(
        start_time=6.0, end_time=9.4, scene_type=SceneType.CHART,
        transcript_text="The company had billions of dollars in debt.",
        visual_goal="Make the scale of the debt legible in one glance.",
        visual_search_queries=[],
        suggested_visual_treatment="Single amber bar growing against a muted grid, value counter locked to the bar head",
        important_text=["$BILLIONS"], animation_type="BAR_GROW", transition_type="CUT",
        sound_effect_suggestion="deep bass thud on impact",
    ),
    dict(
        start_time=9.4, end_time=12.1, scene_type=SceneType.TEXT_ANIMATION,
        transcript_text="Ninety days from insolvency.",
        visual_goal="Let the number carry the whole frame — no imagery competes with it.",
        visual_search_queries=[],
        suggested_visual_treatment="Condensed heading, tight tracking, centred on near-black with a thin amber rule",
        important_text=["90 DAYS"], animation_type="NUMBER_COUNT_UP", transition_type="WHIP_PAN",
        sound_effect_suggestion="clock tick",
    ),
    dict(
        start_time=12.1, end_time=15.8, scene_type=SceneType.PHOTO,
        transcript_text="Steve Jobs returned to Apple.",
        visual_goal="Put a face to the turning point with a recognisable portrait of Jobs from the era.",
        visual_search_queries=["Steve Jobs 1997 Macworld keynote", "Steve Jobs portrait black turtleneck 1997"],
        suggested_visual_treatment="Warm archival grade, subtle 2.5D parallax cut-out, lower third with name and title",
        important_text=["Steve Jobs"], animation_type="PARALLAX_2_5D", transition_type="CROSSFADE",
        sound_effect_suggestion="camera shutter click",
    ),
    dict(
        start_time=15.8, end_time=18.9, scene_type=SceneType.MAP,
        transcript_text="From Cupertino, the decision reached every market at once.",
        visual_goal="Show reach spreading outward from a single point on the map.",
        visual_search_queries=["vintage world map plain", "Cupertino California map"],
        suggested_visual_treatment="Muted topographic map, amber route lines drawing outward, city label typeset in mono",
        important_text=["Cupertino"], animation_type="MAP_ROUTE_REVEAL", transition_type="MATCH_CUT",
        sound_effect_suggestion="soft whoosh per route",
    ),
    dict(
        start_time=18.9, end_time=21.4, scene_type=SceneType.LOGO,
        transcript_text="The bitten apple would come to mean something else entirely.",
        visual_goal="Land the brand mark as the payoff of the sequence.",
        visual_search_queries=["Apple rainbow logo 1997", "Apple logo monochrome"],
        suggested_visual_treatment="Logo isolated on black, slow rack focus from soft to sharp, faint light leak",
        important_text=[], animation_type="SCALE_POP", transition_type="LIGHT_LEAK",
        sound_effect_suggestion=None,
    ),
    dict(
        start_time=21.4, end_time=23.39, scene_type=SceneType.MOTION_GRAPHIC,
        transcript_text="What followed has no comparison in corporate history.",
        visual_goal="Close on an abstract beat that implies scale without a literal image.",
        visual_search_queries=[],
        suggested_visual_treatment="Thin animated line chart abstracted into pure geometry, amber on near-black",
        important_text=[], animation_type="LINE_DRAW", transition_type="CROSSFADE",
        sound_effect_suggestion="sustained cinematic swell",
    ),
]


async def main() -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    if len(sys.argv) > 2 and sys.argv[1] == "--clear":
        project_id = sys.argv[2]
        result = await db.scenes.delete_many({"project_id": project_id})
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"scene_planning": {"status": "idle", "error": None, "scene_count": 0,
                                         "model": None, "segments_planned": 0,
                                         "segments_total": 0, "completed_at": None}}},
        )
        print(f"cleared {result.deleted_count} seeded scenes from {project_id}")
        return

    project_id = sys.argv[1]
    doc = await db.projects.find_one({"id": project_id})
    if not doc:
        raise SystemExit(f"no project {project_id}")

    await db.scenes.delete_many({"project_id": project_id})
    scenes = [
        Scene(project_id=project_id, index=index, **plan).model_dump()
        for index, plan in enumerate(PLANS)
    ]
    await db.scenes.insert_many(scenes)
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"scene_planning": {"status": "ready", "error": None,
                                     "scene_count": len(scenes), "model": "SEEDED (not AI)",
                                     "segments_planned": 0, "segments_total": 0,
                                     "completed_at": None}}},
    )
    print(f"seeded {len(scenes)} verification scenes onto {doc['title']} ({project_id})")


if __name__ == "__main__":
    asyncio.run(main())
