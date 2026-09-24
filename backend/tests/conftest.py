"""Pre-scaffolded pytest fixtures for the FastAPI backend.

Tests hit the live uvicorn process managed by supervisor (not an in-process ASGI app), so
the app under test is the same one the frontend and Playwright see. Do NOT re-create this
file — add app-specific fixtures below the marker at the bottom.
"""

import os

import httpx
import pytest
import pytest_asyncio

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API_URL = f"{BACKEND_URL}/api"


def api_url(path: str = "") -> str:
    """Absolute URL for an /api route: api_url("/status") -> http://localhost:8001/api/status."""
    return f"{API_URL}{path}"


@pytest.fixture(scope="session")
def backend_url() -> str:
    return BACKEND_URL


@pytest.fixture
def client():
    """Sync httpx client rooted at /api — the default for endpoint tests.

    Example:
        def test_status(client):
            assert client.get("/status").status_code == 200
    """
    with httpx.Client(base_url=API_URL, timeout=30.0) as c:
        yield c


@pytest_asyncio.fixture
async def aclient():
    """Async variant, for tests that also await motor/backend helpers directly."""
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as c:
        yield c


# --- app-specific fixtures below this line ---

import filelock

# Cross-process lock (works across xdist workers, each its own OS process) guarding the
# shared 'localstoragestub' supervisor program. test_tscheck_storage_failure_returns_424.py
# stops/starts that process; any test that talks to object storage (uploads, audio GETs)
# must not run while it is intentionally down. Acquire this lock for the duration of any
# storage-touching critical section.
STORAGE_STUB_LOCK_PATH = "/tmp/tscheck-localstoragestub.lock"


@pytest.fixture(scope="session")
def storage_stub_lock() -> filelock.FileLock:
    return filelock.FileLock(STORAGE_STUB_LOCK_PATH)
