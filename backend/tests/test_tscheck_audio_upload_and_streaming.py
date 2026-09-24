"""Criterion: uploading an audio file creates a project; the audio is stored in
object storage and is streamable (200 full request, 206 ranged request)."""

import time

import httpx

AUDIO_FIXTURE = "/tmp/speech23.wav"


def _create_project(client: httpx.Client) -> dict:
    with open(AUDIO_FIXTURE, "rb") as fh:
        resp = client.post(
            "/projects",
            files={"file": ("tscheck-audio-upload.wav", fh, "audio/wav")},
            data={"title": "tscheck-audio-upload"},
        )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_upload_creates_project_with_stored_audio(client: httpx.Client):
    project = _create_project(client)
    project_id = project["id"]
    assert project["title"] == "tscheck-audio-upload"
    assert project["audio"]["object_key"].startswith(f"audio/{project_id}/")
    # duration probed server-side from the real wav container (~23.4s fixture)
    assert project["audio"]["duration_seconds"] is not None
    assert 20 <= project["audio"]["duration_seconds"] <= 27

    # detail fetch reflects the same facts
    detail = client.get(f"/projects/{project_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["audio"]["object_key"] == project["audio"]["object_key"]
    assert body["audio"]["duration_seconds"] is not None


def test_audio_stream_supports_full_and_range_requests(client: httpx.Client):
    project = _create_project(client)
    project_id = project["id"]

    full = client.get(f"/projects/{project_id}/audio")
    assert full.status_code == 200, full.text
    assert len(full.content) > 0

    ranged = client.get(f"/projects/{project_id}/audio", headers={"Range": "bytes=0-999"})
    assert ranged.status_code == 206, ranged.text
    assert "content-range" in ranged.headers
    assert len(ranged.content) == 1000
