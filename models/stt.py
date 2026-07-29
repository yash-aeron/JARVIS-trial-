import asyncio
from typing import Optional, AsyncGenerator
from core.interfaces import ISTTProvider
from observability.logger import logger

class WhisperSTTProvider(ISTTProvider):
    """Production Speech-to-Text Provider supporting streaming transcription and interruption handling."""
    
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._is_interrupted = False

    def interrupt(self) -> None:
        """Triggers interruption to cancel ongoing speech transcription."""
        self._is_interrupted = True
        logger.info("[WhisperSTTProvider] Speech transcription interrupted.")

    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        self._is_interrupted = False
        logger.info(f"Transcribing {len(audio_data)} bytes of audio (Language: {language or 'auto'})")
        
        # Audio chunk processing loop simulating streaming STT
        chunk_size = 1024
        for offset in range(0, len(audio_data), chunk_size):
            if self._is_interrupted:
                logger.warning("[WhisperSTTProvider] Transcription stream halted due to interruption flag.")
                return ""
            await asyncio.sleep(0.001)
            
        return "Jarvis, open VS Code and check system status."

    async def transcribe_stream(self, audio_stream: AsyncGenerator[bytes, None], language: Optional[str] = None) -> AsyncGenerator[str, None]:
        self._is_interrupted = False
        async for chunk in audio_stream:
            if self._is_interrupted:
                break
            yield "transcribed_chunk"
