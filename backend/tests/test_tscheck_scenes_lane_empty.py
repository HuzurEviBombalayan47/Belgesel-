"""Criterion: the visual scenes lane is honestly empty (stage 2 not built) —
GET /api/projects/{id}/scenes must return an empty list, never fabricated data."""

import httpx

AUDIO_FIXTURE = "/tmp/speech23.wav"


def test_scenes_endpoint_returns_empty_list_for_new_project(client: httpx.Client):
    with open(AUDIO_FIXTURE, "rb") as fh:
        resp = client.post(
            "/projects",
            files={"file": ("tscheck-scenes-empty.wav", fh, "audio/wav")},
            data={"title": "tscheck-scenes-empty"},
        )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    scenes_resp = client.get(f"/projects/{project_id}/scenes")
    assert scenes_resp.status_code == 200, scenes_resp.text
    assert scenes_resp.json() == []
