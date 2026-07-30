"""
speech/audio_in.py — Microphone capture for push-to-talk.

Records raw 16 kHz mono PCM while a key is held, exposing a live amplitude level
so the UI can render a waveform during capture.
"""
import threading
from typing import List, Optional

from observability.logger import logger

try:
    import sounddevice as _sd
    import numpy as _np
    _MIC_AVAILABLE = True
except Exception:
    _MIC_AVAILABLE = False

SAMPLE_RATE = 16_000


class MicRecorder:
    """Non-blocking microphone recorder producing 16-bit PCM."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._stream = None
        self._chunks: List[bytes] = []
        self._lock = threading.Lock()
        self._level = 0.0
        self._recording = False

    @property
    def available(self) -> bool:
        return _MIC_AVAILABLE

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def level(self) -> float:
        """Most recent amplitude, normalized 0..1."""
        return self._level

    def start(self) -> bool:
        if not _MIC_AVAILABLE:
            logger.warning("[MicRecorder] sounddevice unavailable — cannot capture audio.")
            return False
        if self._recording:
            return True

        with self._lock:
            self._chunks = []
        self._level = 0.0

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            if status:
                logger.debug(f"[MicRecorder] stream status: {status}")
            mono = indata[:, 0] if indata.ndim > 1 else indata
            pcm = (mono * 32767.0).astype(_np.int16)
            with self._lock:
                self._chunks.append(pcm.tobytes())
            peak = float(_np.abs(mono).max()) if mono.size else 0.0
            # Light smoothing so the waveform doesn't strobe.
            self._level = self._level * 0.6 + min(1.0, peak * 2.2) * 0.4

        try:
            self._stream = _sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=512,
                callback=callback,
            )
            self._stream.start()
            self._recording = True
            logger.info("[MicRecorder] Capture started.")
            return True
        except Exception as exc:
            logger.warning(f"[MicRecorder] Could not open microphone: {exc}")
            self._stream = None
            return False

    def stop(self) -> bytes:
        """Stop capture and return the recorded PCM."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                logger.debug(f"[MicRecorder] Error closing stream: {exc}")
            self._stream = None

        self._recording = False
        self._level = 0.0
        with self._lock:
            data = b"".join(self._chunks)
            self._chunks = []
        logger.info(f"[MicRecorder] Capture stopped ({len(data)} bytes).")
        return data
