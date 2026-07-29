"""
models/tts.py — Edge-TTS provider with real synthesis and interruption.

Real integration path:
    pip install edge-tts

If edge-tts is not installed the class degrades gracefully and logs a warning.

Interruption model:
  - interrupt() sets a flag read between every yielded audio chunk.
  - The flag is reset at the start of each synthesize / synthesize_stream call.
  - SpeechManager calls interrupt() when a new wake-word is detected mid-speech.
"""
import asyncio
import io
from typing import Optional, AsyncGenerator

from core.interfaces import ITTSProvider
from observability.logger import logger

# ── Optional edge-tts import ──────────────────────────────────────────────────
try:
    import edge_tts as _edge_tts
    _EDGETTS_AVAILABLE = True
except ImportError:
    _EDGETTS_AVAILABLE = False
    logger.warning(
        "[EdgeTTSProvider] edge-tts not installed. "
        "Run: pip install edge-tts  — provider will return silent bytes until then."
    )


class EdgeTTSProvider(ITTSProvider):
    """
    Text-to-Speech provider using Microsoft Edge-TTS neural voices.

    Features:
    * Real edge-tts synthesis via SSML WebSocket stream.
    * Interruption flag — call interrupt() between audio chunks.
    * Streaming synthesis — yields MP3 chunks as they arrive from the network.
    * Graceful fallback — returns empty bytes when edge-tts is not installed.
    """

    # Maps language codes to Edge-TTS voice names
    _VOICE_MAP = {
        "en":    "en-US-ChristopherNeural",
        "en-US": "en-US-ChristopherNeural",
        "en-GB": "en-GB-RyanNeural",
        "hi":    "hi-IN-MadhurNeural",
        "fr":    "fr-FR-HenriNeural",
        "de":    "de-DE-ConradNeural",
        "ja":    "ja-JP-KeitaNeural",
    }

    def __init__(self, default_voice: str = "en-US-ChristopherNeural"):
        self.default_voice   = default_voice
        self._is_interrupted = False

    # ── Interruption ───────────────────────────────────────────────────────────
    def interrupt(self) -> None:
        """Signal the current TTS stream to stop at the next chunk boundary."""
        self._is_interrupted = True
        logger.info("[EdgeTTSProvider] TTS interrupted.")

    # ── Voice resolution ───────────────────────────────────────────────────────
    def _resolve_voice(self, voice: Optional[str], language: Optional[str]) -> str:
        if voice:
            return voice
        if language:
            return self._VOICE_MAP.get(language, self.default_voice)
        return self.default_voice

    # ── Batch synthesis ────────────────────────────────────────────────────────
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bytes:
        self._is_interrupted = False
        target_voice = self._resolve_voice(voice, language)
        logger.info(f"[EdgeTTSProvider] Synthesizing '{text[:60]}' with voice '{target_voice}'")

        if not _EDGETTS_AVAILABLE:
            logger.warning("[EdgeTTSProvider] edge-tts unavailable — returning silent bytes.")
            return b""

        try:
            communicate = _edge_tts.Communicate(text, voice=target_voice)
            audio_buf   = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buf.write(chunk["data"])
            audio_bytes = audio_buf.getvalue()
            logger.info(f"[EdgeTTSProvider] Synthesized {len(audio_bytes)} bytes.")
            return audio_bytes
        except Exception as exc:
            logger.error(f"[EdgeTTSProvider] Synthesis error: {exc}")
            return b""

    # ── Streaming synthesis ────────────────────────────────────────────────────
    async def synthesize_stream(
        self,
        text_stream: AsyncGenerator[str, None],
        voice: Optional[str] = None,
        language: Optional[str] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Consume a stream of text tokens, yield audio chunks as soon as they
        are synthesized.  Sentence-buffers tokens before calling edge-tts so
        each network round-trip covers a natural speech unit (~1–2 sentences).
        """
        self._is_interrupted = False
        target_voice = self._resolve_voice(voice, language)
        logger.info(f"[EdgeTTSProvider] Starting streaming synthesis with voice '{target_voice}'")

        FLUSH_CHARS = 120   # flush buffer after this many chars (~1 sentence)

        if not _EDGETTS_AVAILABLE:
            logger.warning("[EdgeTTSProvider] edge-tts unavailable — streaming yields nothing.")
            async for _ in text_stream:
                pass
            return

        token_buf = ""
        async for token in text_stream:
            if self._is_interrupted:
                logger.info("[EdgeTTSProvider] Stream interrupted before flush.")
                break
            token_buf += token

            # Flush on sentence boundaries or when buffer is large enough
            ends_sentence = any(token_buf.rstrip().endswith(p) for p in (".", "!", "?", "..."))
            if ends_sentence or len(token_buf) >= FLUSH_CHARS:
                async for audio_chunk in self._synthesize_segment(token_buf, target_voice):
                    if self._is_interrupted:
                        return
                    yield audio_chunk
                token_buf = ""

        # Flush remaining buffer
        if token_buf.strip() and not self._is_interrupted:
            async for audio_chunk in self._synthesize_segment(token_buf, target_voice):
                if self._is_interrupted:
                    return
                yield audio_chunk

    async def _synthesize_segment(self, text: str, voice: str) -> AsyncGenerator[bytes, None]:
        """Internal: synthesize a single text segment, yield raw MP3 chunks."""
        try:
            communicate = _edge_tts.Communicate(text.strip(), voice=voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as exc:
            logger.error(f"[EdgeTTSProvider] Segment synthesis error: {exc}")
