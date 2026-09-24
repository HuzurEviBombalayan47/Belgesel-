"""Criteria:
- Planning endpoint guards wrong states with correct status codes (409 not-ready,
  404 unknown project for plan and delete).
- DELETE clears a plan so it can be re-run (verified against the seeded project, which
  is restored via tools_seed_demo_scenes.py afterwards so later checks/demo still have
  data).

Uses a fresh /tmp/speech23.wav upload for the 409 case (transcription starts out
'pending'/'processing', not 'ready') and fires the plan request immediately.
"""

import subprocess
import sys
import time
from pathlib import Path

import httpx

FIXTURE = "/tmp/speech23.wav"
BACKEND_DIR = Path(__file__).resolve().parents[1]
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


def _find_seeded_project(client: httpx.Client) -> dict:
    resp = client.get("/projects")
    assert resp.status_code == 200, resp.text
    for p in resp.json():
        if p["title"] == "SEEDED UI CHECK (not AI output)":
            return p
    raise AssertionError("seeded project not found - reseed with tools_seed_demo_scenes.py")


def test_plan_returns_409_when_transcription_not_ready(client: httpx.Client):
    with open(FIXTURE, "rb") as fh:
        resp = client.post(
            "/projects",
            files={"file": ("tscheck-not-ready.wav", fh, "audio/wav")},
        )
    assert resp.status_code == 201, resp.text
    project = resp.json()
    project_id = project["id"]

    # Fire immediately - transcription is still pending/processing right after upload.
    plan_resp = client.post(f"/projects/{project_id}/scenes/plan")
    assert plan_resp.status_code == 409, plan_resp.text
    detail = plan_resp.json().get("detail", "")
    assert detail, "expected an explanatory detail on 409"


def test_plan_returns_404_for_unknown_project(client: httpx.Client):
    resp = client.post(f"/projects/{UNKNOWN_ID}/scenes/plan")
    assert resp.status_code == 404, resp.text


def test_delete_scenes_returns_404_for_unknown_project(client: httpx.Client):
    resp = client.delete(f"/projects/{UNKNOWN_ID}/scenes")
    assert resp.status_code == 404, resp.text


def test_delete_clears_plan_then_restores_seeded_project(client: httpx.Client):
    project = _find_seeded_project(client)
    project_id = project["id"]

    # Sanity: seeded project has scenes before we touch it.
    before = client.get(f"/projects/{project_id}/scenes")
    assert before.status_code == 200
    assert len(before.json()) == 8

    try:
        del_resp = client.delete(f"/projects/{project_id}/scenes")
        assert del_resp.status_code == 200, del_resp.text
        body = del_resp.json()
        assert body.get("deleted", body.get("deleted_count", 0)) in (8,) or any(
            v == 8 for v in body.values() if isinstance(v, int)
        ), body

        after = client.get(f"/projects/{project_id}/scenes")
        assert after.status_code == 200
        assert after.json() == []

        proj_after = client.get(f"/projects/{project_id}").json()
        assert proj_after["scene_planning"]["status"] == "idle", proj_after["scene_planning"]
    finally:
        # Restore the seeded plan unconditionally so later checks/demo keep their data.
        result = subprocess.run(
            [sys.executable, "tools_seed_demo_scenes.py", project_id],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        time.sleep(0.5)

    restored = client.get(f"/projects/{project_id}/scenes")
    assert restored.status_code == 200
    assert len(restored.json()) == 8
