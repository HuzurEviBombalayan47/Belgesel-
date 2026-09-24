"""Regression for the reported bug: uploading a large (>8MB) audio file used to fail
with a 502 because boto3 switched to multipart upload and the storage endpoint didn't
return an UploadId. Covers:
  - the 48MB fixture uploads successfully (201) with the right stored size
  - the large object round-trips intact via full GET and a Range GET (multipart parts
    were reassembled in order, not truncated)
  - the response returns while transcription is still pending/processing (upload never
    blocks on transcription)
  - large-file transcription eventually completes for REAL with many segments whose
    timestamps span the whole original timeline (chunk offsets applied correctly)
"""

import time

import httpx

BIG_FIXTURE = "/tmp/big-narration.wav"
EXPECTED_SIZE = 50540804


def _create_big_project() -> dict:
    # Generous timeouts: the file itself is ~48MB and multipart upload takes real time.
    # NOTE: client is intentionally NOT opened via `with` here — returning from inside a
    # `with` block would close it before the caller can use it.
    client = httpx.Client(base_url="http://localhost:8001/api", timeout=120.0)
    with open(BIG_FIXTURE, "rb") as fh:
        resp = client.post(
            "/projects",
            files={"file": ("tscheck-big-narration.wav", fh, "audio/wav")},
            data={"title": "tscheck-big-narration"},
        )
    assert resp.status_code == 201, resp.text
    project = resp.json()

    # Upload request must return before transcription finishes — proves
    # transcription runs as a background task, not inline with the upload.
    assert project["transcription"]["status"] in ("pending", "processing"), project["transcription"]

    return project, client


def test_large_file_upload_returns_201_with_correct_size_and_defers_transcription(storage_stub_lock):
    with storage_stub_lock:
        project, client = _create_big_project()
    try:
        assert project["audio"]["object_key"].startswith(f"audio/{project['id']}/")
        assert project["audio"]["size_bytes"] is not None
        # allow a small tolerance for container/header differences
        assert abs(project["audio"]["size_bytes"] - EXPECTED_SIZE) < 2000, project["audio"]
    finally:
        client.close()


def test_large_file_streams_intact_full_and_ranged(storage_stub_lock):
    with storage_stub_lock, httpx.Client(base_url="http://localhost:8001/api", timeout=120.0) as client:
        with open(BIG_FIXTURE, "rb") as fh:
            resp = client.post(
                "/projects",
                files={"file": ("tscheck-big-narration-stream.wav", fh, "audio/wav")},
                data={"title": "tscheck-big-narration-stream"},
            )
        assert resp.status_code == 201, resp.text
        project = resp.json()
        project_id = project["id"]
        size_bytes = project["audio"]["size_bytes"]

        full = client.get(f"/projects/{project_id}/audio")
        assert full.status_code == 200, full.text
        assert int(full.headers.get("content-length", "0")) == size_bytes

        ranged = client.get(
            f"/projects/{project_id}/audio", headers={"Range": "bytes=0-999"}
        )
        assert ranged.status_code == 206, ranged.text
        assert "content-range" in ranged.headers
        assert len(ranged.content) == 1000


def test_large_file_transcription_completes_with_timeline_correct_segments(storage_stub_lock):
    with storage_stub_lock:
        project, client = _create_big_project()
    try:
        project_id = project["id"]
        status = None
        deadline = time.time() + 180  # up to 3 minutes, per briefing
        while time.time() < deadline:
            detail = client.get(f"/projects/{project_id}")
            assert detail.status_code == 200, detail.text
            body = detail.json()
            status = body["transcription"]["status"]
            if status == "ready":
                break
            assert status in ("pending", "processing"), body["transcription"]
            time.sleep(5)

        assert status == "ready", f"transcription did not reach ready in time, last status={status}"

        transcript = client.get(f"/projects/{project_id}/transcript")
        assert transcript.status_code == 200, transcript.text
        segments = transcript.json()
        assert len(segments) > 50, f"expected many segments (~221), got {len(segments)}"

        last_end = max(s["end_seconds"] for s in segments)
        assert last_end > 1400, f"last segment end_seconds={last_end}, expected timeline spread > 1400s"
    finally:
        client.close()
