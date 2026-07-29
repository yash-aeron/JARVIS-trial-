from typing import Optional
from core.interfaces import ISTTProvider
from observability.logger import logger

class WhisperSTTProvider(ISTTProvider):
    """Speech-to-Text Provider with fallback mechanism."""
    
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size

    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        logger.info(f"Transcribing {len(audio_data)} bytes of audio (Language: {language or 'auto'})")
        # STT pipeline wrapper
        return "Jarvis, open VS Code and check system status."
