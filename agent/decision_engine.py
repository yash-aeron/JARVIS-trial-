from pydantic import BaseModel, Field
from typing import Optional

class AgentDecisionModel(BaseModel):
    correlation_id: str
    needs_planning: bool
    needs_memory: bool
    needs_vision: bool
    needs_internet: bool
    needs_clarification: bool
    is_dangerous: bool = False
    clarification_prompt: Optional[str] = None

class DecisionEngine:
    """Executive decision engine assessing request scope and safety."""
    
    def evaluate(self, utterance: str, intent_category: str, correlation_id: str) -> AgentDecisionModel:
        text_lower = utterance.lower()
        
        needs_planning = (intent_category == "MULTI_STEP_PLAN")
        needs_memory = any(w in text_lower for w in ["remember", "last time", "history", "notes", "my preference"])
        needs_vision = any(w in text_lower for w in ["screen", "see", "look", "window", "ocr"])
        needs_internet = any(w in text_lower for w in ["weather", "news", "search", "download", "browse"])
        is_dangerous = any(w in text_lower for w in ["delete", "shutdown", "format", "wipe", "rm -rf"])
        
        return AgentDecisionModel(
            correlation_id=correlation_id,
            needs_planning=needs_planning,
            needs_memory=needs_memory,
            needs_vision=needs_vision,
            needs_internet=needs_internet,
            needs_clarification=False,
            is_dangerous=is_dangerous
        )
