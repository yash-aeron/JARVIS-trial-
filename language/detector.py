import re
from typing import Dict, Any, List

class CodeSwitchLanguageDetector:
    """Detects primary language and code-switching markers (e.g. Hindi-English mixed commands)."""
    
    HINDI_KEYWORDS = ["kholo", "chalao", "dikhao", "karo", "batao", "kya", "kaise", "samjhaao"]

    def detect(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        has_hindi = any(re.search(r'\b' + re.escape(kw) + r'\b', text_lower) for kw in self.HINDI_KEYWORDS)
        
        if has_hindi:
            return {
                "primary_language": "hi-IN",
                "code_switching": True,
                "detected_languages": ["en-US", "hi-IN"]
            }
        return {
            "primary_language": "en-US",
            "code_switching": False,
            "detected_languages": ["en-US"]
        }
