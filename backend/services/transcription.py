"""Speech-to-text seam — stage 1 ships the REAL implementation: Whisper (`whisper-1`)
via the Emergent LLM universal key, producing timestamped segments.

Notes:
- The transcription API accepts files up to 25 MB per request. Chunked transcription of
  longer files is a stage-2 extension of this service; until then larger files get a
  clear, honest "failed" state on the project (audio upload/playback is unaffected).
- The service returns raw timing data; the worker (routers/projects.py) maps it onto
  TranscriptSegment rows, keeping this module free of storage concerns.
"""

import os
from dataclasses import dataclass
from typing import Protocol

from lib.audio_prep import AudioChunk, downmix_wav, is_wav, split_wav

WHISPER_MODEL = "whisper-1"
MAX_TRANSCRIBE_BYTES = 24 * 1024 * 1024  # keep safely under the API's 25 MB request cap


class AudioTooLargeForTranscription(RuntimeError):
    pass


@dataclass
class RawSegment:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass
class TranscriptionResult:
    segments: list[RawSegment]
    language: str | None = None


class TranscriptionService(Protocol):
    model_name: str

    async def transcribe(self, audio_path: str) -> TranscriptionResult: ...


class WhisperTranscription:
    model_name = WHISPER_MODEL

    def __init__(self, api_key: str) -> None:
        from emergentintegrations.llm.openai import OpenAISpeechToText

        self._stt = OpenAISpeechToText(api_key=api_key)

    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        chunks, cleanup = self._prepare(audio_path)
        try:
            all_segments: list[RawSegment] = []
            language: str | None = None
            for chunk in chunks:
                result = await self._transcribe_one(chunk.path)
                language = language or result.language
                for segment in result.segments:
                    all_segments.append(
                        RawSegment(
                            start_seconds=round(segment.start_seconds + chunk.offset_seconds, 3),
                            end_seconds=round(segment.end_seconds + chunk.offset_seconds, 3),
                            text=segment.text,
                        )
                    )
            all_segments.sort(key=lambda segment: segment.start_seconds)
            return TranscriptionResult(segments=all_segments, language=language)
        finally:
            for path in cleanup:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _prepare(self, audio_path: str) -> tuple[list[AudioChunk], list[str]]:
        """Keep real transcription working for long narrations: oversized WAVs are
        downmixed to 16 kHz mono and split into chunks under the request cap."""
        size = os.path.getsize(audio_path)
        if size <= MAX_TRANSCRIBE_BYTES:
            return [AudioChunk(path=audio_path, offset_seconds=0.0, temporary=False)], []

        if not is_wav(audio_path):
            raise AudioTooLargeForTranscription(
                f"audio is {size / (1024 * 1024):.1f} MB — the transcription API accepts 25 MB "
                "per request, and this compressed format cannot be split in-pod. Upload a "
                "shorter file or a WAV, which is split automatically."
            )

        cleanup: list[str] = []
        working = downmix_wav(audio_path)
        cleanup.append(working)
        if os.path.getsize(working) <= MAX_TRANSCRIBE_BYTES:
            return [AudioChunk(path=working, offset_seconds=0.0, temporary=True)], cleanup

        chunks = split_wav(working, MAX_TRANSCRIBE_BYTES)
        cleanup.extend(chunk.path for chunk in chunks)
        return chunks, cleanup

    async def _transcribe_one(self, path: str) -> TranscriptionResult:
        with open(path, "rb") as handle:
            response = await self._stt.transcribe(
                file=handle,
                model=WHISPER_MODEL,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                temperature=0.0,
            )

        # The provider returns segments as plain dicts (litellm TranscriptionResponse);
        # older/other builds may hand back objects. Read both shapes.
        def field(segment: object, name: str, default: object = None) -> object:
            if isinstance(segment, dict):
                return segment.get(name, default)
            return getattr(segment, name, default)

        raw_segments = getattr(response, "segments", None)
        if raw_segments is None and isinstance(response, dict):
            raw_segments = response.get("segments")

        segments: list[RawSegment] = []
        for seg in raw_segments or []:
            text = str(field(seg, "text", "") or "").strip()
            if not text:
                continue
            start = float(field(seg, "start", 0.0) or 0.0)
            end = float(field(seg, "end", 0.0) or 0.0)
            if end < start:
                end = start
            segments.append(RawSegment(start_seconds=round(start, 3), end_seconds=round(end, 3), text=text))

        # Whisper omits segments when only a flat transcript comes back — keep the text
        # rather than silently reporting an empty transcript.
        if not segments:
            flat = str(getattr(response, "text", "") or "").strip()
            if flat:
                total = getattr(response, "duration", None)
                segments.append(
                    RawSegment(
                        start_seconds=0.0,
                        end_seconds=round(float(total), 3) if total else 0.0,
                        text=flat,
                    )
                )

        language = getattr(response, "language", None)
        return TranscriptionResult(segments=segments, language=str(language) if language else None)


_service: TranscriptionService | None = None
_resolved = False


def get_transcription_service() -> TranscriptionService | None:
    """Whisper implementation when enabled AND configured, else None.
    Enabled by default whenever EMERGENT_LLM_KEY exists; set TRANSCRIPTION_ENABLED=false
    in backend/.env to opt out."""
    global _service, _resolved
    if not _resolved:
        _resolved = True
        enabled = os.environ.get("TRANSCRIPTION_ENABLED", "true").strip().lower() not in {"false", "0", "no"}
        api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
        if enabled and api_key:
            _service = WhisperTranscription(api_key)
    return _service


def transcription_configured() -> bool:
    return get_transcription_service() is not None
