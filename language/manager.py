from typing import Optional
from config.settings import Settings
from language.detector import LanguageDetector
from core.models import LanguageDetectionModel
from observability.logger import logger

class LanguageManager:
    """Manages active language context and maps appropriate voices for speech synthesis."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings
        self.detector = LanguageDetector()
        self.active_language = "en-US"

    def process_utterance(self, text: str) -> LanguageDetectionModel:
        detection = self.detector.detect(text)
        self.active_language = detection.language
        return detection

    def get_voice_for_language(self, language: Optional[str] = None) -> str:
        target_lang = language or self.active_language
        if "hi" in target_lang.lower():
            return "hi-IN-SwaraNeural"
        return "en-US-ChristopherNeural"
