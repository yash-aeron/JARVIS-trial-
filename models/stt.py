"""
models/stt.py — Faster-Whisper STT provider.

Real integration path:
    pip install faster-whisper

If faster-whisper is not installed the class still loads and returns an empty
string, emitting a clear WARNING so the developer knows what to install.

Pipeline per chunk:
    raw PCM bytes
        ↓ SileroVAD.is_speech()
        ↓ (drop silent chunks)
        ↓ faster_whisper.WhisperModel.transcribe()
        ↓ yield text segments
        ↓ WakeWordDetector.push_token()  [streaming only]
"""
import asyncio
import io
import struct
import wave
from typing import Optional, AsyncGenerator

from core.interfaces import ISTTProvider
from speech.vad import SileroVAD
from speech.wake_word import WakeWordDetector
from observability.logger import logger

# ── Optional faster-whisper import ────────────────────────────────────────────
try:
    from faster_whisper import WhisperModel as _WhisperModel
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False
    logger.warning(
        "[FasterWhisperSTT] faster-whisper not installed. "
        "Run: pip install faster-whisper  — provider will return empty strings until then."
    )


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16_000, channels: int = 1) -> bytes:
    """Wrap raw 16-bit LE PCM in a minimal WAV container so Whisper can read it."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)        # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class FasterWhisperSTTProvider(ISTTProvider):
    """
    Production STT provider using Faster-Whisper.

    Features:
    * Silero VAD gate — silent chunks never reach the model.
    * Interruption flag — call interrupt() from any coroutine.
    * Streaming transcription — yields text segments as they arrive.
    * Wake-word awareness — push_token() is called per streaming segment.
    """

    def __init__(
        self,
        model_size: str = "base",
        compute_type: str = "int8",          # int8 is fast on CPU; use float16 on GPU
        device: str = "cpu",
        sample_rate: int = 16_000,
        vad_threshold: float = 0.45,
    ):
        self.model_size     = model_size
        self.compute_type   = compute_type
        self.device         = device
        self.sample_rate    = sample_rate
        self._is_interrupted = False
        self.vad            = SileroVAD(threshold=vad_threshold, sampling_rate=sample_rate)
        self.wake_word      = WakeWordDetector()
        self._model: Optional[object] = None

    # ── Lazy model loading ─────────────────────────────────────────────────────
    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if not _WHISPER_AVAILABLE:
            return False
        try:
            logger.info(f"[FasterWhisperSTT] Loading model '{self.model_size}' on {self.device} ({self.compute_type})...")
            self._model = _WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("[FasterWhisperSTT] Model loaded.")
            return True
        except Exception as exc:
            logger.error(f"[FasterWhisperSTT] Model load failed: {exc}")
            return False

    # ── Interruption ───────────────────────────────────────────────────────────
    def interrupt(self) -> None:
        """Signal any running transcription to stop at the next chunk boundary."""
        self._is_interrupted = True
        logger.info("[FasterWhisperSTT] Interruption flagged.")

    # ── Batch transcription ────────────────────────────────────────────────────
    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        self._is_interrupted = False
        self.vad.reset_states()

        if not audio_data:
            return ""

        # VAD gate — skip if no speech energy detected
        if not self.vad.is_speech(audio_data):
            logger.debug("[FasterWhisperSTT] VAD: no speech, skipping transcription.")
            return ""

        if not self._ensure_model():
            logger.warning("[FasterWhisperSTT] Primary model unavailable — invoking SpeechRecognition fallback.")
            return await self._fallback_transcribe(audio_data, language)

        # Run Whisper in a thread-pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        try:
            wav_bytes = _pcm_to_wav(audio_data, self.sample_rate)
            wav_io    = io.BytesIO(wav_bytes)
            segments, _info = await loop.run_in_executor(
                None,
                lambda: self._model.transcribe(
                    wav_io,
                    language=language,
                    beam_size=5,
                    vad_filter=True,        # Whisper's own VAD as second pass
                    word_timestamps=False,
                ),
            )
            text = " ".join(seg.text.strip() for seg in segments)
            logger.info(f"[FasterWhisperSTT] Transcribed: '{text[:80]}'")
            return text
        except Exception as exc:
            logger.error(f"[FasterWhisperSTT] Primary transcription error: {exc}. Invoking fallback...")
            return await self._fallback_transcribe(audio_data, language)

    async def _fallback_transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        """Fallback transcription using SpeechRecognition engine."""
        def _recognize():
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                wav_bytes = _pcm_to_wav(audio_data, self.sample_rate)
                with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                    audio = recognizer.record(source)
                return recognizer.recognize_google(audio, language=language or "en-US")
            except Exception as e:
                logger.debug(f"[FasterWhisperSTT] SpeechRecognition fallback unavailable: {e}")
                return ""
        return await asyncio.to_thread(_recognize)

    # ── Streaming transcription ────────────────────────────────────────────────
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Consume an async stream of PCM chunks, yield transcript tokens as they arrive.

        Each chunk is VAD-gated.  If the model is unavailable, yields nothing.
        Respects the interrupt() flag between chunks.
        """
        self._is_interrupted = False
        self.vad.reset_states()
        self.wake_word.reset()

        if not self._ensure_model():
            logger.warning("[FasterWhisperSTT] Model unavailable — streaming yields nothing.")
            async for _ in audio_stream:   # drain the stream
                pass
            return

        loop = asyncio.get_event_loop()
        pcm_buffer = bytearray()

        # Accumulate ~300ms of audio before sending to Whisper (chunk-based streaming)
        FLUSH_BYTES = self.sample_rate * 2 * 1  # 1 second of 16-bit mono PCM

        async for chunk in audio_stream:
            if self._is_interrupted:
                logger.info("[FasterWhisperSTT] Stream interrupted.")
                break

            if not chunk:
                continue

            # VAD gate per chunk
            if not self.vad.is_speech(chunk):
                continue

            pcm_buffer.extend(chunk)

            if len(pcm_buffer) >= FLUSH_BYTES:
                wav_bytes = _pcm_to_wav(bytes(pcm_buffer), self.sample_rate)
                wav_io    = io.BytesIO(wav_bytes)
                pcm_buffer.clear()

                try:
                    segments, _ = await loop.run_in_executor(
                        None,
                        lambda: self._model.transcribe(
                            wav_io,
                            language=language,
                            beam_size=3,       # lower beam for lower latency
                            vad_filter=True,
                        ),
                    )
                    for seg in segments:
                        if self._is_interrupted:
                            break
                        token = seg.text.strip()
                        if token:
                            self.wake_word.push_token(token)
                            yield token
                except Exception as exc:
                    logger.error(f"[FasterWhisperSTT] Streaming error: {exc}")

        # Flush any remaining buffered audio
        if pcm_buffer and not self._is_interrupted:
            try:
                wav_bytes = _pcm_to_wav(bytes(pcm_buffer), self.sample_rate)
                wav_io    = io.BytesIO(wav_bytes)
                segments, _ = await loop.run_in_executor(
                    None,
                    lambda: self._model.transcribe(wav_io, language=language, beam_size=3, vad_filter=True),
                )
                for seg in segments:
                    token = seg.text.strip()
                    if token:
                        self.wake_word.push_token(token)
                        yield token
            except Exception as exc:
                logger.error(f"[FasterWhisperSTT] Flush error: {exc}")


class WhisperSTTProvider(FasterWhisperSTTProvider):
    """Alias for backward compatibility."""
    pass
