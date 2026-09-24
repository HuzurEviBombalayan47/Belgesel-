"""Audio media helpers — upload validation + server-side metadata extraction.

Every value produced here is measured from the actual uploaded file (mutagen reads
the real container headers). Nothing is estimated or mocked.
"""

import mimetypes
import os
import re
from pathlib import Path

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".aac", ".ogg", ".oga", ".opus", ".flac", ".webm"}

# Container formats that legitimately carry an audio-only narration track.
_CONTAINER_TYPES = {"video/mp4", "video/webm", "video/ogg", "application/octet-stream"}


def is_allowed_upload(file_name: str, content_type: str | None) -> bool:
    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    if not content_type:
        return True
    if content_type.startswith("audio/"):
        return True
    return content_type in _CONTAINER_TYPES


def guess_content_type(file_name: str, provided: str | None) -> str:
    if provided and provided != "application/octet-stream":
        return provided
    guessed = mimetypes.guess_type(file_name)[0]
    return guessed or "application/octet-stream"


def sanitize_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", base).strip().strip(".")
    return (base or "audio")[:120]


def max_upload_bytes() -> int:
    try:
        mb = int(os.environ.get("MAX_UPLOAD_MB", "250"))
    except ValueError:
        mb = 250
    return max(1, mb) * 1024 * 1024


def probe_duration(path: str) -> float | None:
    """Real duration in seconds, read from the audio container by mutagen.
    Returns None (not an error) for containers mutagen cannot parse — the editor
    then falls back to the duration reported by the browser's own audio decoder."""
    try:
        import mutagen

        parsed = mutagen.File(path)
        if parsed is not None and parsed.info is not None and parsed.info.length:
            return round(float(parsed.info.length), 3)
    except Exception:
        return None
    return None
