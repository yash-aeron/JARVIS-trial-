from pydantic import BaseModel, Field
from typing import Optional

class AgentDecisionModel(BaseModel):
    correlation_id: str
    confidence: float = 0.90
    needs_planning: bool
    needs_memory: bool
    needs_vision: bool
    needs_web: bool
    needs_clarification: bool
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    clarification_prompt: Optional[str] = None

class DecisionEngine:
    """Executive decision engine assessing request scope, confidence, risk levels, and clarification needs."""
    
    def evaluate(self, utterance: str, intent_category: str, correlation_id: str) -> AgentDecisionModel:
        text_lower = utterance.lower()
        
        needs_planning = (intent_category == "MULTI_STEP_PLAN")
        needs_memory = any(w in text_lower for w in ["remember", "last time", "history", "notes", "my preference"])
        needs_vision = any(w in text_lower for w in ["screen", "see", "look", "window", "ocr"])
        needs_web = any(w in text_lower for w in ["weather", "news", "search", "download", "browse"])
        
        risk_level = "LOW"
        if any(w in text_lower for w in ["delete", "shutdown", "format", "wipe", "rm -rf"]):
            risk_level = "CRITICAL"
        elif any(w in text_lower for w in ["install", "update", "git push", "write"]):
            risk_level = "MEDIUM"
            
        confidence = 0.95 if any(w in text_lower for w in ["open", "launch", "kholo", "run", "hello", "hi"]) else 0.40
        needs_clarification = (confidence < 0.50)
        
        clarification_prompt = "Could you please clarify your request?" if needs_clarification else None
        
        return AgentDecisionModel(
            correlation_id=correlation_id,
            confidence=confidence,
            needs_planning=needs_planning,
            needs_memory=needs_memory,
            needs_vision=needs_vision,
            needs_web=needs_web,
            needs_clarification=needs_clarification,
            risk_level=risk_level,
            clarification_prompt=clarification_prompt
        )
