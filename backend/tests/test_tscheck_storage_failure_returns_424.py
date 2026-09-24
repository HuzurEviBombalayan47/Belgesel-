"""Criterion: when the storage dependency is unreachable, the API returns the ACTUAL
backend reason as HTTP 424 with a JSON body (not a 502/503 gateway page), and the app
recovers once the dependency comes back.

This test stops/starts the supervisor program 'localstoragestub' — it restores it in a
finally block so it never leaves the shared environment broken for other tests/checks.
"""

import subprocess
import time

import httpx

FIXTURE = "/tmp/speech23.wav"


def _supervisorctl(*args: str) -> None:
    subprocess.run(["sudo", "supervisorctl", *args], check=True, capture_output=True, timeout=30)


def test_storage_down_returns_424_with_actionable_detail_then_recovers(storage_stub_lock):
    with storage_stub_lock, httpx.Client(base_url="http://localhost:8001/api", timeout=30.0) as client:
        _supervisorctl("stop", "localstoragestub")
        try:
            # give the client library a moment to notice the port is closed
            time.sleep(1)
            with open(FIXTURE, "rb") as fh:
                resp = client.post(
                    "/projects",
                    files={"file": ("tscheck-storage-down.wav", fh, "audio/wav")},
                    data={"title": "tscheck-storage-down"},
                )
            assert resp.status_code == 424, resp.text
            assert resp.headers.get("content-type", "").startswith("application/json"), resp.headers
            detail = resp.json().get("detail", "")
            assert "object storage" in detail.lower(), detail
            assert ("r2_endpoint_url" in detail.lower()) or ("r2_account_id" in detail.lower()), detail
        finally:
            _supervisorctl("start", "localstoragestub")
            time.sleep(3)

        # recovery: a subsequent upload succeeds again
        with open(FIXTURE, "rb") as fh:
            resp2 = client.post(
                "/projects",
                files={"file": ("tscheck-storage-recovered.wav", fh, "audio/wav")},
                data={"title": "tscheck-storage-recovered"},
            )
        assert resp2.status_code == 201, resp2.text
