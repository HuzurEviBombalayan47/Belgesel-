"""Object storage layer — Cloudflare R2 (S3-compatible) is the ONLY storage backend.

Design contract (stage 1):
- Every binary asset (audio today; scene assets, renders, exports later) flows through
  the R2 storage client — nothing is persisted to local disk.
- R2 is addressed via the S3 API with path-style addressing. Credentials + bucket come
  from backend/.env: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET.
- When those keys are missing the layer raises StorageNotConfigured, which server.py
  converts into a clear 503 so the UI can show a setup state instead of pretending to
  store data. There is deliberately NO local-disk fallback.
- R2_ENDPOINT_URL optionally overrides the endpoint (e.g. an S3-compatible endpoint for
  integration testing); the default is the standard R2 endpoint for the account.
- boto3 is synchronous, so every call is pushed to a worker thread with asyncio.to_thread
  — the FastAPI event loop is never blocked.
"""

import asyncio
import os
import tempfile
from typing import Iterator

import boto3
from botocore.config import Config

from lib.errors import StorageNotConfigured


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


class R2Storage:
    """Cloudflare R2 via the S3-compatible API."""

    provider = "cloudflare_r2"

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        endpoint_url: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url or f"https://{account_id}.r2.cloudflarestorage.com"
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=10,
                read_timeout=120,
            ),
        )

    # ---- writes -------------------------------------------------------------
    async def upload_file(self, path: str, key: str, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.upload_file,
            Filename=path,
            Bucket=self.bucket,
            Key=key,
            ExtraArgs={"ContentType": content_type},
        )

    # ---- reads --------------------------------------------------------------
    async def head(self, key: str) -> dict:
        return await asyncio.to_thread(self._client.head_object, Bucket=self.bucket, Key=key)

    async def get(self, key: str, range_header: str | None = None) -> dict:
        kwargs: dict = {"Bucket": self.bucket, "Key": key}
        if range_header:
            kwargs["Range"] = range_header
        return await asyncio.to_thread(self._client.get_object, **kwargs)

    async def download_to_temp(self, key: str, suffix: str = "") -> str:
        """Stream the object back to a temp file (used by re-runs of analysis jobs)."""
        fd, path = tempfile.mkstemp(prefix="r2dl-", suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as handle:
                await asyncio.to_thread(self._client.download_fileobj, self.bucket, key, handle)
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        return path

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self.bucket, Key=key)

    def presigned_get(self, key: str, expires: int = 3600) -> str:
        """Stage-2 hook: direct-to-CDN playback URLs. Stage 1 streams via the API."""
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires
        )


def iter_body(body, chunk_size: int = 256 * 1024) -> Iterator[bytes]:
    """Adapt a blocking botocore StreamingBody to a generator for StreamingResponse
    (starlette pumps sync iterators through a thread pool)."""
    try:
        while True:
            chunk = body.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        try:
            body.close()
        except Exception:
            pass


_storage: R2Storage | None = None
_resolved = False


def get_storage() -> R2Storage:
    """Singleton accessor. Raises StorageNotConfigured when the R2_* env keys are missing."""
    global _storage, _resolved
    if not _resolved:
        _resolved = True
        account_id = _env("R2_ACCOUNT_ID")
        access_key_id = _env("R2_ACCESS_KEY_ID")
        secret_access_key = _env("R2_SECRET_ACCESS_KEY")
        bucket = _env("R2_BUCKET")
        if account_id and access_key_id and secret_access_key and bucket:
            _storage = R2Storage(
                account_id,
                access_key_id,
                secret_access_key,
                bucket,
                endpoint_url=_env("R2_ENDPOINT_URL"),
            )
    if _storage is None:
        raise StorageNotConfigured(
            "Object storage (Cloudflare R2) is not configured — set R2_ACCOUNT_ID, "
            "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_BUCKET in backend/.env"
        )
    return _storage


def storage_configured() -> bool:
    try:
        get_storage()
        return True
    except StorageNotConfigured:
        return False
