"""Criterion: R2 storage and real Whisper transcription were not swapped out for a
mock/local fallback. GET /api/system/status reports the real provider names, and a
static read of the storage/transcription modules shows no local-disk substitution."""

from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_system_status_reports_r2_and_whisper(client: httpx.Client):
    resp = client.get("/system/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["storage"]["provider"] == "cloudflare_r2", body["storage"]
    assert body["storage"]["configured"] is True, body["storage"]

    assert body["transcription"]["configured"] is True, body["transcription"]
    assert body["transcription"]["model"] == "whisper-1", body["transcription"]

    assert body["scene_planning"]["configured"] is True, body["scene_planning"]
    assert body["scene_planning"]["model"] == "gemini-2.5-flash", body["scene_planning"]


def test_storage_module_has_no_local_disk_fallback():
    source = (BACKEND_DIR / "lib" / "storage.py").read_text()
    lowered = source.lower()
    # The real upload/download path must talk to S3/R2 (boto3), not silently write to
    # a local directory as a substitute for object storage.
    assert "boto3" in lowered or "aioboto3" in lowered, "expected an S3/R2 client library"
    forbidden_fallback_markers = [
        "shutil.copy",
        "local disk fallback",
        "fallback to local",
    ]
    for marker in forbidden_fallback_markers:
        assert marker not in lowered, f"found disk-fallback marker '{marker}' in storage.py"


def test_transcription_module_is_not_mocked():
    source = (BACKEND_DIR / "services" / "transcription.py").read_text()
    lowered = source.lower()
    assert "whisper-1" in lowered, "expected the real whisper-1 model name"
    forbidden_mock_markers = [
        "return \"mock transcript\"",
        "fake transcription",
        "stubbed transcription",
    ]
    for marker in forbidden_mock_markers:
        assert marker not in lowered, f"found mock marker '{marker}' in transcription.py"
