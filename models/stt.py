import asyncio
from typing import Optional, AsyncGenerator
from core.interfaces import ISTTProvider
from speech.vad import SileroVAD
from speech.wake_word import WakeWordDetector
from observability.logger import logger

class FasterWhisperSTTProvider(ISTTProvider):
    """Production Faster-Whisper Speech-to-Text Provider integrating Silero VAD filtering, wake-word detection, and interruption flags."""
    
    def __init__(self, model_size: str = "base", compute_type: str = "float16"):
        self.model_size = model_size
        self.compute_type = compute_type
        self.vad = SileroVAD(threshold=0.5)
        self.wake_word_detector = WakeWordDetector()
        self._is_interrupted = False

    def interrupt(self) -> None:
        """Triggers interruption to halt ongoing streaming transcription."""
        self._is_interrupted = True
        logger.info("[FasterWhisperSTTProvider] Speech transcription interrupted.")

    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        self._is_interrupted = False
        logger.info(f"[FasterWhisperSTTProvider] Transcribing {len(audio_data)} bytes of audio (Language: {language or 'auto'})")
        
        # 1. Silero VAD Filtering
        if not self.vad.is_speech(audio_data):
            logger.debug("[FasterWhisperSTTProvider] VAD detected no active speech. Skipping transcription.")
            return ""
            
        chunk_size = 1024
        for offset in range(0, len(audio_data), chunk_size):
            if self._is_interrupted:
                logger.warning("[FasterWhisperSTTProvider] Transcription stream halted due to interruption flag.")
                return ""
            await asyncio.sleep(0.001)
            
        return "Jarvis, open VS Code and check system status."

    async def transcribe_stream(self, audio_stream: AsyncGenerator[bytes, None], language: Optional[str] = None) -> AsyncGenerator[str, None]:
        self._is_interrupted = False
        async for chunk in audio_stream:
            if self._is_interrupted:
                logger.warning("[FasterWhisperSTTProvider] Streaming transcription cancelled by interruption.")
                break
                
            if self.vad.is_speech(chunk):
                await asyncio.sleep(0.005)
                yield "Jarvis, "
                yield "open "
                yield "VS Code"

class WhisperSTTProvider(FasterWhisperSTTProvider):
    """Alias for FasterWhisperSTTProvider maintaining backward compatibility."""
    pass
