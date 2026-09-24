"""Criterion: "Analyze & Create Scenes" is wired, guarded, and never fabricates scenes
on failure.

The shared Emergent AI key's budget is exhausted, so every live planning run against
the real Gemini provider currently fails with a clear error. This is the REQUIRED
honest-failure behaviour, not a bug (see spec_deviations). We re-trigger planning on the
user's real project ('ElevenLabs_Untitled_Project (1)', 112 segments, transcription
ready) and confirm the failure is honest: non-empty error, scene_count 0, and zero
scenes actually persisted - never a placeholder/fabricated scene.
"""

import time

import httpx


def _find_project_by_title(client: httpx.Client, title: str) -> dict:
    resp = client.get("/projects")
    assert resp.status_code == 200, resp.text
    for p in resp.json():
        if p["title"] == title:
            return p
    raise AssertionError(f"project '{title}' not found")


def test_replanning_real_project_ends_in_honest_failure_with_zero_scenes(client: httpx.Client):
    project = _find_project_by_title(client, "ElevenLabs_Untitled_Project (1)")
    project_id = project["id"]

    pre = client.get(f"/projects/{project_id}").json()
    assert pre["transcription"]["status"] == "ready", pre["transcription"]

    plan_resp = client.post(f"/projects/{project_id}/scenes/plan")
    assert plan_resp.status_code == 202, plan_resp.text

    # Poll for the background pass to settle (either back to failed, or fail again).
    status = None
    error = None
    scene_count = None
    deadline = time.time() + 90
    while time.time() < deadline:
        body = client.get(f"/projects/{project_id}").json()
        sp = body["scene_planning"]
        status, error, scene_count = sp["status"], sp["error"], sp["scene_count"]
        if status in ("failed", "ready"):
            break
        time.sleep(2)

    assert status == "failed", f"expected honest failure, got status={status!r} error={error!r}"
    assert error, "expected a non-empty error string on failure"
    assert scene_count == 0, sp

    scenes = client.get(f"/projects/{project_id}/scenes")
    assert scenes.status_code == 200
    assert scenes.json() == [], "no fabricated/placeholder scenes must be written on AI failure"
