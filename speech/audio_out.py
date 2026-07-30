"""
speech/audio_out.py — Audio playback for synthesized speech.

edge-tts returns MP3 bytes and pyttsx3 returns WAV; both are decoded to PCM and
pushed to the default output device. Playback is interruptible so a new wake-word
can cut off an in-progress reply.
"""
import asyncio
import io
import shutil
import subprocess
import threading
import wave
from typing import Optional

from observability.logger import logger

try:
    import sounddevice as _sd
    import numpy as _np
    _AUDIO_AVAILABLE = True
except Exception:
    _AUDIO_AVAILABLE = False


class AudioPlayer:
    """Decodes and plays speech audio on the default output device."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def interrupt(self) -> None:
        self._stop.set()
        if _AUDIO_AVAILABLE:
            try:
                _sd.stop()
            except Exception:
                pass

    async def play(self, audio_bytes: bytes) -> bool:
        """Play audio, returning True if it actually reached the speakers."""
        if not audio_bytes:
            return False
        if not _AUDIO_AVAILABLE:
            logger.warning("[AudioPlayer] sounddevice/numpy unavailable — cannot play audio.")
            return False

        self._stop.clear()
        return await asyncio.to_thread(self._play_blocking, audio_bytes)

    def _play_blocking(self, audio_bytes: bytes) -> bool:
        decoded = self._decode_wav(audio_bytes)
        if decoded is None:
            decoded = self._decode_via_ffmpeg(audio_bytes)
        if decoded is None:
            logger.warning("[AudioPlayer] Could not decode audio payload.")
            return False

        samples, rate, channels = decoded
        if self._stop.is_set():
            return False

        try:
            # Serialize playback so overlapping replies don't fight for the device.
            with self._lock:
                _sd.play(samples, samplerate=rate)
                _sd.wait()
            return not self._stop.is_set()
        except Exception as exc:
            logger.warning(f"[AudioPlayer] Playback error: {exc}")
            return False

    @staticmethod
    def _decode_wav(audio_bytes: bytes):
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                channels = wf.getnchannels()
                rate = wf.getframerate()
                width = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())
            if width != 2:
                return None
            arr = _np.frombuffer(frames, dtype=_np.int16)
            if channels > 1:
                arr = arr.reshape(-1, channels)
            return arr, rate, channels
        except Exception:
            return None

    @staticmethod
    def _decode_via_ffmpeg(audio_bytes: bytes):
        """Decode MP3 (edge-tts output) to PCM using ffmpeg when available."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            logger.warning(
                "[AudioPlayer] ffmpeg not found — MP3 speech cannot be decoded. "
                "Install ffmpeg to enable spoken replies."
            )
            return None
        try:
            proc = subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
                 "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", "24000", "pipe:1"],
                input=audio_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            if proc.returncode != 0 or not proc.stdout:
                return None
            arr = _np.frombuffer(proc.stdout, dtype=_np.int16)
            return arr, 24000, 1
        except Exception as exc:
            logger.warning(f"[AudioPlayer] ffmpeg decode failed: {exc}")
            return None
