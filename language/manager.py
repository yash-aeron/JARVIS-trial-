from typing import Dict, Any, Optional
from language.detector import CodeSwitchLanguageDetector
from config.settings import Settings

class LanguageManager:
    """Centralized Language Manager coordinating STT/TTS languages and code-switching."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.detector = CodeSwitchLanguageDetector()
        self.active_language = settings.get("system.default_language", "en-US")

    def process_utterance(self, text: str) -> Dict[str, Any]:
        detection_result = self.detector.detect(text)
        if detection_result["code_switching"]:
            self.active_language = detection_result["primary_language"]
        return detection_result

    def get_voice_for_language(self, lang: Optional[str] = None) -> str:
        target_lang = lang or self.active_language
        if target_lang.startswith("hi"):
            return "hi-IN-SwaraNeural"
        return "en-US-ChristopherNeural"
