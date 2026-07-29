"""
speech/speech_manager.py — Full streaming speech pipeline.

Flow (continuous listen loop):
    mic chunks  →  SileroVAD  →  [discard silence]
                →  WakeWordDetector.push_token()  →  [arm]
                →  FasterWhisperSTT.transcribe_stream()  →  transcript
                →  JARVISApp.process_user_command()
                →  EdgeTTSProvider.synthesize_stream()  →  audio out

Interruption:
    A new wake-word mid-TTS calls interrupt() on both STT and TTS providers,
    then immediately re-arms the listen loop.
"""
import asyncio
import uuid
from typing import Optional, AsyncGenerator, Callable, Awaitable

from core.interfaces import IService, ISTTProvider, ITTSProvider, IEventBus
from core.models import EventModel, SpeechRecognizedEventData, SpeechSpokeEventData
from state.state_manager import StateManager
from state.states import AssistantState
from language.manager import LanguageManager
from speech.vad import SileroVAD
from speech.wake_word import WakeWordDetector
from observability.logger import logger


class SpeechManager(IService):
    """
    Orchestrates the full real-time speech pipeline:
        microphone → VAD → wake-word → Whisper STT → intent/exec → Edge-TTS

    Key design decisions:
    * VAD is applied at two levels: inside SileroVAD (per-chunk) and inside
      FasterWhisperSTT (second-pass Whisper VAD filter).
    * WakeWordDetector runs in streaming mode (push_token) so it can trigger
      mid-sentence without waiting for a full utterance to complete.
    * Interruption is cooperative: both STT and TTS expose interrupt() which
      sets an asyncio-safe flag checked at every chunk boundary.
    * speak() and speak_stream() are separated so callers can choose between
      whole-response synthesis (lower latency start) and streaming (lower
      time-to-first-audio).
    """

    def __init__(
        self,
        stt: ISTTProvider,
        tts: ITTSProvider,
        language_manager: LanguageManager,
        state_manager: StateManager,
        event_bus: Optional[IEventBus] = None,
    ):
        self._stt              = stt
        self._tts              = tts
        self._language_manager = language_manager
        self._state_manager    = state_manager
        self._event_bus        = event_bus

        # VAD and wake-word run at the SpeechManager level as well as inside
        # the STT provider — belt-and-suspenders for the listen loop.
        self.vad               = SileroVAD(threshold=0.45)
        self.wake_word_detector = WakeWordDetector(keyphrase="jarvis", cooldown_sec=2.0)

        self._speaking         = False
        self._listen_task: Optional[asyncio.Task] = None

    # ── IService ───────────────────────────────────────────────────────────────
    @property
    def name(self) -> str:
        return "SpeechManager"

    async def start(self) -> None:
        self.vad.reset_states()
        self.wake_word_detector.reset()
        logger.info("[SpeechManager] Started — Silero VAD + Wake-Word + Faster-Whisper + Edge-TTS ready.")

    async def stop(self) -> None:
        self.interrupt()
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
        logger.info("[SpeechManager] Stopped.")

    async def health_check(self) -> bool:
        return True

    # ── Interruption ───────────────────────────────────────────────────────────
    def interrupt(self) -> None:
        """
        Interrupt any running STT transcription or TTS synthesis.
        Safe to call from any coroutine or thread.
        """
        if hasattr(self._stt, "interrupt"):
            self._stt.interrupt()
        if hasattr(self._tts, "interrupt"):
            self._tts.interrupt()
        self._speaking = False
        logger.info("[SpeechManager] Pipeline interrupted.")

    # ── Continuous listen loop ─────────────────────────────────────────────────
    async def run_listen_loop(
        self,
        mic_stream: AsyncGenerator[bytes, None],
        on_utterance: Callable[[str, str], Awaitable[None]],
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Consume mic_stream (raw 16-bit LE PCM at 16 kHz) indefinitely.

        For each utterance detected after a wake-word:
          1. Feeds speech chunks to Whisper for streaming transcription.
          2. Calls on_utterance(transcript, cid) for intent/exec handling.
          3. Any mid-speech wake-word triggers interrupt() before re-arming.

        Args:
            mic_stream:    Async generator of raw PCM bytes from the microphone.
            on_utterance:  Async callback receiving (transcript, correlation_id).
        """
        cid = correlation_id or str(uuid.uuid4())
        self._state_manager.transition_to(AssistantState.LISTENING, "Listen loop started", correlation_id=cid)
        self.vad.reset_states()
        self.wake_word_detector.reset()

        armed      = False   # True after wake-word, collecting utterance chunks
        speech_buf: list[bytes] = []

        async for raw_chunk in mic_stream:
            # ── VAD gate ────────────────────────────────────────────────────────
            if not self.vad.is_speech(raw_chunk):
                if armed and speech_buf:
                    # Silence after speech — flush what we have
                    await self._flush_and_dispatch(speech_buf, on_utterance, cid)
                    speech_buf.clear()
                    armed = False
                    self.wake_word_detector.reset()
                    self._state_manager.transition_to(
                        AssistantState.LISTENING, "Waiting for wake-word", correlation_id=cid
                    )
                continue

            # ── Wake-word detection (streaming) ─────────────────────────────────
            if not armed:
                # Lightweight check: run a quick non-blocking Whisper pass on
                # a small buffer to get tokens for the wake-word detector.
                # For low-latency setups this can be replaced with a dedicated
                # small acoustic model (e.g. openWakeWord).
                quick_text = await self._quick_transcribe(raw_chunk)
                if quick_text and self.wake_word_detector.push_token(quick_text):
                    logger.info("[SpeechManager] Wake-word armed — collecting utterance.")
                    armed = True
                    cid   = str(uuid.uuid4())   # fresh CID per utterance
                    speech_buf.clear()
                continue

            # ── Collect utterance ────────────────────────────────────────────────
            speech_buf.append(raw_chunk)

            # Interrupt if wake-word fires again mid-utterance (user correcting)
            quick_text = await self._quick_transcribe(raw_chunk)
            if quick_text and self.wake_word_detector.push_token(quick_text):
                logger.info("[SpeechManager] Interrupt — new wake-word while collecting utterance.")
                self.interrupt()
                speech_buf.clear()
                armed = True
                cid   = str(uuid.uuid4())

    # ── Batch speech input ─────────────────────────────────────────────────────
    async def process_speech_input(
        self,
        audio_data: bytes,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Transcribe a complete audio buffer (non-streaming path)."""
        cid = correlation_id or str(uuid.uuid4())
        self._state_manager.transition_to(AssistantState.LISTENING, "Speech input received", correlation_id=cid)

        if not self.vad.is_speech(audio_data):
            logger.debug("[SpeechManager] VAD: no speech in audio buffer.")
            self._state_manager.transition_to(AssistantState.IDLE, "No speech", correlation_id=cid)
            return ""

        text = await self._stt.transcribe(audio_data, language=self._language_manager.active_language)

        if text:
            lang_res = self._language_manager.process_utterance(text)
            await self._publish_recognized(text, lang_res, cid)

        return text

    # ── Streaming speech input ─────────────────────────────────────────────────
    async def process_streaming_input(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        correlation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Transcribe a streaming audio source, yielding text tokens."""
        cid = correlation_id or str(uuid.uuid4())
        self._state_manager.transition_to(AssistantState.LISTENING, "Streaming input", correlation_id=cid)

        tokens: list[str] = []
        async for token in self._stt.transcribe_stream(
            audio_stream, language=self._language_manager.active_language
        ):
            tokens.append(token)
            yield token

        full_text = " ".join(tokens)
        if full_text:
            lang_res = self._language_manager.process_utterance(full_text)
            await self._publish_recognized(full_text, lang_res, cid)

    # ── Batch TTS ──────────────────────────────────────────────────────────────
    async def speak(
        self,
        text: str,
        language: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Synthesize text to audio (batch).  Interruptible via interrupt()."""
        cid = correlation_id or str(uuid.uuid4())
        self._state_manager.transition_to(AssistantState.SPEAKING, "Synthesizing speech", correlation_id=cid)
        self._speaking = True
        voice = self._language_manager.get_voice_for_language(language)

        audio_bytes = await self._tts.synthesize(text, voice=voice, language=language)
        self._speaking = False

        if self._event_bus:
            payload = SpeechSpokeEventData(text=text, voice=voice, audio_length=len(audio_bytes))
            await self._event_bus.publish(
                EventModel(correlation_id=cid, topic="speech.spoke", payload=payload, sender="SpeechManager")
            )

        self._state_manager.transition_to(AssistantState.IDLE, "Speech completed", correlation_id=cid)

    # ── Streaming TTS ──────────────────────────────────────────────────────────
    async def speak_stream(
        self,
        text_stream: AsyncGenerator[str, None],
        language: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS synthesis — yields audio chunks as text tokens arrive.
        Interruptible: interrupt() stops synthesis between chunks.
        """
        cid = correlation_id or str(uuid.uuid4())
        self._state_manager.transition_to(AssistantState.SPEAKING, "Streaming synthesis", correlation_id=cid)
        self._speaking  = True
        voice           = self._language_manager.get_voice_for_language(language)
        total_bytes     = 0

        async for audio_chunk in self._tts.synthesize_stream(text_stream, voice=voice, language=language):
            if not self._speaking:
                break
            total_bytes += len(audio_chunk)
            yield audio_chunk

        self._speaking = False
        if self._event_bus:
            payload = SpeechSpokeEventData(text="streaming_response", voice=voice, audio_length=total_bytes)
            await self._event_bus.publish(
                EventModel(correlation_id=cid, topic="speech.spoke", payload=payload, sender="SpeechManager")
            )
        self._state_manager.transition_to(AssistantState.IDLE, "Stream complete", correlation_id=cid)

    # ── Internal helpers ───────────────────────────────────────────────────────
    async def _quick_transcribe(self, pcm_chunk: bytes) -> str:
        """
        Non-blocking, low-latency single-chunk transcription for wake-word
        checking.  Falls through to the STT provider without VAD (already
        gated by the caller).
        """
        try:
            text = await self._stt.transcribe(pcm_chunk, language=None)
            return text
        except Exception:
            return ""

    async def _flush_and_dispatch(
        self,
        speech_buf: list[bytes],
        on_utterance: Callable[[str, str], Awaitable[None]],
        cid: str,
    ) -> None:
        full_audio = b"".join(speech_buf)
        self._state_manager.transition_to(AssistantState.THINKING, "Processing utterance", correlation_id=cid)
        text = await self._stt.transcribe(full_audio, language=self._language_manager.active_language)
        if text:
            lang_res = self._language_manager.process_utterance(text)
            await self._publish_recognized(text, lang_res, cid)
            await on_utterance(text, cid)

    async def _publish_recognized(self, text: str, lang_res: object, cid: str) -> None:
        if self._event_bus:
            payload = SpeechRecognizedEventData(text=text, language_details=lang_res)
            await self._event_bus.publish(
                EventModel(
                    correlation_id=cid,
                    topic="speech.recognized",
                    payload=payload,
                    sender="SpeechManager",
                )
            )
