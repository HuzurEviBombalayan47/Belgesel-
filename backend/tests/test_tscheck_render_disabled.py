"""Criterion: render button/API honestly reports stage-2 disabled — POST renders
must answer 501 with a detail mentioning stage 2, never a fabricated success."""

import httpx

AUDIO_FIXTURE = "/tmp/speech23.wav"


def test_create_render_returns_501_stage_two(client: httpx.Client):
    with open(AUDIO_FIXTURE, "rb") as fh:
        resp = client.post(
            "/projects",
            files={"file": ("tscheck-render-disabled.wav", fh, "audio/wav")},
            data={"title": "tscheck-render-disabled"},
        )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    render_resp = client.post(f"/projects/{project_id}/renders")
    assert render_resp.status_code == 501, render_resp.text
    detail = render_resp.json().get("detail", "")
    assert "stage 2" in detail.lower(), detail
