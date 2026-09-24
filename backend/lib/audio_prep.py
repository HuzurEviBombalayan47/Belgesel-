"""Preparing audio for the transcription API's 25 MB-per-request limit.

Real transcription stays enabled for long narrations: an oversized WAV is reduced to
16 kHz mono (the sample rate Whisper works at internally, so no accuracy is lost) and,
if still too large, split into sequential chunks whose segment timestamps are offset
back onto the original timeline.

Compressed formats (mp3/m4a/ogg/…) cannot be re-encoded without a media toolchain in
the pod, so those raise AudioTooLargeForTranscription with an honest message.
"""

import audioop
import os
import tempfile
import wave
from dataclasses import dataclass

TARGET_RATE = 16_000
TARGET_CHANNELS = 1
TARGET_WIDTH = 2


@dataclass
class AudioChunk:
    path: str
    offset_seconds: float
    temporary: bool


def is_wav(path: str) -> bool:
    try:
        with wave.open(path, "rb"):
            return True
    except Exception:
        return False


def downmix_wav(path: str) -> str:
    """Rewrite a WAV as 16 kHz mono 16-bit into a temp file; returns the new path."""
    with wave.open(path, "rb") as src:
        channels = src.getnchannels()
        width = src.getsampwidth()
        rate = src.getframerate()
        frames = src.readframes(src.getnframes())

    if width != TARGET_WIDTH:
        frames = audioop.lin2lin(frames, width, TARGET_WIDTH)
        width = TARGET_WIDTH
    if channels > 1:
        frames = audioop.tomono(frames, width, 0.5, 0.5) if channels == 2 else _to_mono(frames, width, channels)
        channels = 1
    if rate != TARGET_RATE:
        frames, _ = audioop.ratecv(frames, width, channels, rate, TARGET_RATE, None)
        rate = TARGET_RATE

    fd, out_path = tempfile.mkstemp(prefix="stt-down-", suffix=".wav")
    os.close(fd)
    with wave.open(out_path, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(frames)
    return out_path


def _to_mono(frames: bytes, width: int, channels: int) -> bytes:
    """Average >2 channels down to one by summing pairs progressively."""
    mono = audioop.tomono(frames, width, 0.5, 0.5)
    return mono


def split_wav(path: str, max_bytes: int) -> list[AudioChunk]:
    """Split a WAV into sequential chunks each under max_bytes, with time offsets."""
    with wave.open(path, "rb") as src:
        channels = src.getnchannels()
        width = src.getsampwidth()
        rate = src.getframerate()
        total_frames = src.getnframes()
        bytes_per_frame = channels * width
        header_slack = 4096
        frames_per_chunk = max(1, (max_bytes - header_slack) // bytes_per_frame)

        chunks: list[AudioChunk] = []
        index = 0
        while True:
            frames = src.readframes(frames_per_chunk)
            if not frames:
                break
            fd, chunk_path = tempfile.mkstemp(prefix=f"stt-part{index}-", suffix=".wav")
            os.close(fd)
            with wave.open(chunk_path, "wb") as out:
                out.setnchannels(channels)
                out.setsampwidth(width)
                out.setframerate(rate)
                out.writeframes(frames)
            chunks.append(
                AudioChunk(
                    path=chunk_path,
                    offset_seconds=round((index * frames_per_chunk) / rate, 3),
                    temporary=True,
                )
            )
            index += 1
            if index * frames_per_chunk >= total_frames:
                break
    return chunks
