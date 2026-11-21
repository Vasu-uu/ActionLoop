"""Audio/video transcription with faster-whisper (local). ffmpeg is used to normalise input."""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from ..config import get_settings

log = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".webm"}
_model = None
_lock = threading.Lock()


class TranscriptionError(RuntimeError):
    """User-friendly transcription failure."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def convert_to_wav(src: Path, dst: Path) -> None:
    """Convert any supported media to 16 kHz mono PCM wav (what Whisper wants)."""
    if not ffmpeg_available():
        raise TranscriptionError("ffmpeg is not installed. Install it (https://ffmpeg.org) to transcribe audio or video.")
    cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(dst)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired as e:
        raise TranscriptionError("Converting the media file took too long.") from e
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size < 1000:
        log.warning("ffmpeg failed: %s", proc.stderr[-500:])
        raise TranscriptionError("This file could not be decoded. Is it a valid, non-empty audio/video file with an audio track?")


def _read_wav(path: Path):
    """Load the 16 kHz mono PCM wav that ffmpeg produced as float32 (avoids a second decoder in PyAV)."""
    import wave

    import numpy as np

    with wave.open(str(path), "rb") as w:
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def get_model():
    global _model
    with _lock:
        if _model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:  # pragma: no cover
                raise TranscriptionError("faster-whisper is not installed. Run: pip install faster-whisper") from e
            s = get_settings()
            device = s.whisper_device
            compute = s.whisper_compute_type
            if device == "auto":
                try:
                    import ctranslate2

                    device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
                except Exception:  # noqa: BLE001
                    device = "cpu"
            if compute == "auto":
                compute = "float16" if device == "cuda" else "int8"
            attempts = [(device, compute)]
            if device != "cpu" and s.whisper_device == "auto":
                attempts.append(("cpu", "int8"))  # GPU present but unusable -> fall back to CPU
            last: Exception | None = None
            for dev, comp in attempts:
                try:
                    log.info("Loading Whisper model %s on %s (%s)", s.whisper_model, dev, comp)
                    m = WhisperModel(s.whisper_model, device=dev, compute_type=comp)
                    if dev == "cuda":  # loading can succeed while the first inference fails; probe it
                        import numpy as np

                        list(m.transcribe(np.zeros(16000, dtype="float32"))[0])
                    _model = m
                    break
                except Exception as e:  # noqa: BLE001
                    last = e
                    log.warning("Whisper on %s/%s failed: %s", dev, comp, e)
            if _model is None:
                raise TranscriptionError(
                    f"Could not load Whisper model '{s.whisper_model}' (first run downloads it and needs internet once): {last}"
                ) from last
    return _model


def transcribe_file(path: Path) -> dict:
    """Return {'text', 'language', 'duration', 'segments': [{start,end,text}]}."""
    with tempfile.TemporaryDirectory(prefix="actionloop_") as tmp:
        wav = Path(tmp) / "audio.wav"
        convert_to_wav(path, wav)
        model = get_model()
        try:
            audio = _read_wav(wav)
            segs, info = model.transcribe(audio, vad_filter=True, beam_size=5)  # language auto-detected
            segments = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs if s.text.strip()]
        except Exception as e:  # noqa: BLE001
            raise TranscriptionError(f"Transcription failed: {e}") from e
    if not segments:
        raise TranscriptionError("No speech was detected in this file.")
    return {
        "text": " ".join(s["text"] for s in segments), "language": getattr(info, "language", None),
        "duration": getattr(info, "duration", None), "segments": segments,
    }
