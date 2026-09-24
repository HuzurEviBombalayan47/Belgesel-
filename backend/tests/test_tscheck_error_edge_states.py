"""Criterion: error and edge states are honest — unknown project 404s, and a
non-audio upload is rejected with 415."""

import io

import httpx


def test_unknown_project_returns_404(client: httpx.Client):
    resp = client.get("/projects/unknown-id")
    assert resp.status_code == 404, resp.text


def test_non_audio_upload_returns_415(client: httpx.Client):
    fake_file = io.BytesIO(b"localhost\n")
    resp = client.post(
        "/projects",
        files={"file": ("tscheck-hostname.txt", fake_file, "text/plain")},
        data={"title": "tscheck-non-audio"},
    )
    assert resp.status_code == 415, resp.text
