from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ExecutiveDecision:
    needs_planning: bool
    needs_memory: bool
    needs_vision: bool
    needs_internet: bool
    needs_clarification: bool
    clarification_prompt: str = ""

class DecisionEngine:
    """Executive decision engine deciding whether planning, memory, vision, internet, or clarification is needed."""
    
    def evaluate(self, utterance: str, intent_category: str) -> ExecutiveDecision:
        text_lower = utterance.lower()
        
        needs_planning = (intent_category == "MULTI_STEP_PLAN")
        needs_memory = any(w in text_lower for w in ["remember", "last time", "history", "notes", "my preference"])
        needs_vision = any(w in text_lower for w in ["screen", "see", "look", "window", "ocr"])
        needs_internet = any(w in text_lower for w in ["weather", "news", "search", "download", "browse"])
        
        return ExecutiveDecision(
            needs_planning=needs_planning,
            needs_memory=needs_memory,
            needs_vision=needs_vision,
            needs_internet=needs_internet,
            needs_clarification=False
        )
