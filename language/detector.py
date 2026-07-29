import re
from core.models import LanguageDetectionModel
from observability.logger import logger

class LanguageDetector:
    """Detects primary language and code-switching markers in natural language utterances."""
    
    HINDI_KEYWORDS = ["kholo", "chalo", "kaise", "batao", "kya", "shuru", "band", "banao", "dikhao", "madad"]

    def detect(self, text: str) -> LanguageDetectionModel:
        text_lower = text.lower()
        words = re.findall(r'\w+', text_lower)
        
        hindi_count = sum(1 for w in words if w in self.HINDI_KEYWORDS)
        
        if hindi_count > 0:
            logger.info(f"Detected Hinglish code-switching in text: '{text[:30]}...'")
            return LanguageDetectionModel(
                language="hi-IN",
                confidence=min(1.0, 0.6 + (hindi_count * 0.15)),
                is_code_switching=True
            )
            
        return LanguageDetectionModel(
            language="en-US",
            confidence=1.0,
            is_code_switching=False
        )
