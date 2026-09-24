"""Criterion: Scene API returns the full structured plan for every scene.

Uses the clearly-labelled seeded project ("SEEDED UI CHECK (not AI output)") which
carries 8 hand-written scene rows spanning 8 scene types. We look the project up by
title rather than hardcoding its id so the test survives re-seeding.
"""

import httpx

ALLOWED_SCENE_TYPES = {
    "PHOTO", "VIDEO", "HISTORICAL_IMAGE", "DOCUMENT", "MAP", "CHART",
    "TEXT_ANIMATION", "MOTION_GRAPHIC", "LOGO", "SCREENSHOT", "MIXED",
}

REQUIRED_FIELDS = [
    "id", "project_id", "index", "start_time", "end_time", "transcript_text",
    "scene_type", "visual_goal", "visual_search_queries", "suggested_visual_treatment",
    "important_text", "animation_type", "transition_type", "sound_effect_suggestion",
    "status", "asset_ids",
]


def _find_seeded_project(client: httpx.Client) -> dict:
    resp = client.get("/projects")
    assert resp.status_code == 200, resp.text
    projects = resp.json()
    for p in projects:
        if p["title"] == "SEEDED UI CHECK (not AI output)":
            return p
    raise AssertionError("seeded project 'SEEDED UI CHECK (not AI output)' not found - reseed with tools_seed_demo_scenes.py")


def test_scenes_endpoint_returns_full_structured_plan(client: httpx.Client):
    project = _find_seeded_project(client)
    resp = client.get(f"/projects/{project['id']}/scenes")
    assert resp.status_code == 200, resp.text
    scenes = resp.json()
    assert len(scenes) == 8, f"expected 8 seeded scenes, got {len(scenes)}"

    for scene in scenes:
        for field in REQUIRED_FIELDS:
            assert field in scene, f"scene {scene.get('index')} missing field '{field}'"
        assert isinstance(scene["visual_search_queries"], list)
        assert isinstance(scene["important_text"], list)
        assert scene["asset_ids"] == [], "asset_ids must be empty at this stage"
        assert scene["scene_type"] in ALLOWED_SCENE_TYPES, scene["scene_type"]
        assert scene["sound_effect_suggestion"] is None or isinstance(scene["sound_effect_suggestion"], str)

    types_present = {s["scene_type"] for s in scenes}
    assert len(types_present) >= 6, f"expected varied scene types, got {types_present}"

    # The CHART scene is a generated-visual case: empty visual_search_queries.
    chart_scenes = [s for s in scenes if s["scene_type"] == "CHART"]
    assert chart_scenes, "expected a CHART scene in the seeded plan"
    assert chart_scenes[0]["visual_search_queries"] == [], "CHART scene should be generated, not searched"


def test_project_scene_planning_subdocument_reflects_seeded_state(client: httpx.Client):
    project = _find_seeded_project(client)
    resp = client.get(f"/projects/{project['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sp = body["scene_planning"]
    assert sp["status"] == "ready", sp
    assert sp["scene_count"] == 8, sp
    assert sp["model"] == "SEEDED (not AI)", sp
