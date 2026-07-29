from typing import Optional
from observability.logger import logger

class WakeWordDetector:
    """Wake-Word Detection engine monitoring continuous audio streams for keyphrases ('Jarvis', 'Hey Jarvis')."""
    
    def __init__(self, keyphrase: str = "jarvis", sensitivity: float = 0.7):
        self.keyphrase = keyphrase.lower()
        self.sensitivity = sensitivity

    def detect_wake_word(self, transcript_chunk: str) -> bool:
        chunk_lower = transcript_chunk.lower()
        if self.keyphrase in chunk_lower or "hey jarvis" in chunk_lower or "jarvis" in chunk_lower:
            logger.info(f"[WakeWordDetector] Wake word '{self.keyphrase}' detected in text stream!")
            return True
        return False
