import asyncio
from typing import Optional, AsyncGenerator
from core.interfaces import ITTSProvider
from observability.logger import logger

class EdgeTTSProvider(ITTSProvider):
    """Text-to-Speech Provider using EdgeTTS/System speech backend with stream synthesis support."""
    
    def __init__(self, default_voice: str = "en-US-ChristopherNeural"):
        self.default_voice = default_voice

    async def synthesize(self, text: str, voice: Optional[str] = None, language: Optional[str] = None) -> bytes:
        target_voice = voice or self.default_voice
        logger.info(f"Synthesizing audio for text: '{text[:40]}...' using voice '{target_voice}'")
        return b"RIFF_AUDIO_DATA_SIMULATED"

    async def synthesize_stream(
        self, 
        text_stream: AsyncGenerator[str, None], 
        voice: Optional[str] = None, 
        language: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        target_voice = voice or self.default_voice
        logger.info(f"[EdgeTTSProvider] Starting audio stream synthesis with voice '{target_voice}'")
        async for token in text_stream:
            await asyncio.sleep(0.005)
            yield f"AUDIO_CHUNK_{token}".encode('utf-8')
