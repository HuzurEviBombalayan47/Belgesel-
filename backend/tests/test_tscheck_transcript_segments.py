"""Criterion: transcript segments with timestamps become available after real
Whisper transcription completes (polling, not instant)."""

import time

import httpx

AUDIO_FIXTURE = "/tmp/speech23.wav"


def test_transcription_completes_and_transcript_lists_segments(client: httpx.Client):
    with open(AUDIO_FIXTURE, "rb") as fh:
        resp = client.post(
            "/projects",
            files={"file": ("tscheck-transcript.wav", fh, "audio/wav")},
            data={"title": "tscheck-transcript"},
        )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    status = None
    deadline = time.time() + 40
    while time.time() < deadline:
        detail = client.get(f"/projects/{project_id}")
        assert detail.status_code == 200
        status = detail.json()["transcription"]["status"]
        if status == "ready":
            break
        assert status in ("pending", "processing"), f"unexpected status {status}"
        time.sleep(2)

    assert status == "ready", f"transcription did not complete in time, last status={status}"

    segments_resp = client.get(f"/projects/{project_id}/transcript")
    assert segments_resp.status_code == 200, segments_resp.text
    segments = segments_resp.json()
    assert len(segments) >= 1
    first = segments[0]
    assert "start_seconds" in first and "end_seconds" in first
    assert isinstance(first["text"], str) and first["text"].strip()
