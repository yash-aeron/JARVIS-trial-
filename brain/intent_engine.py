from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Any, List, Optional
from core.interfaces import ILLMProvider
from observability.logger import logger

class IntentCategory(Enum):
    CONVERSATION = auto()
    MULTI_STEP_PLAN = auto()
    SINGLE_TOOL = auto()
    SYSTEM_CONTROL = auto()
    QUERY_MEMORY = auto()
    REJECT = auto()

@dataclass
class IntentResult:
    category: IntentCategory
    capabilities_needed: List[str]
    confidence: float
    raw_utterance: str

class IntentEngine:
    """Classifies user utterances into actionable Intent Categories."""
    
    def __init__(self, llm_provider: ILLMProvider):
        self.llm = llm_provider

    async def classify(self, utterance: str, context: Optional[Dict[str, Any]] = None) -> IntentResult:
        text_lower = utterance.lower()
        
        # Rule-based fast paths for instant classification
        if any(w in text_lower for w in ["open", "run", "launch", "clone", "install", "search for", "search"]):
            if any(w in text_lower for w in ["and", "then", "after", "also"]):
                return IntentResult(
                    category=IntentCategory.MULTI_STEP_PLAN,
                    capabilities_needed=["app_automation", "terminal", "web_search"],
                    confidence=0.95,
                    raw_utterance=utterance
                )
            return IntentResult(
                category=IntentCategory.SINGLE_TOOL,
                capabilities_needed=["app_automation"],
                confidence=0.90,
                raw_utterance=utterance
            )
            
        if any(w in text_lower for w in ["who", "what", "how", "why", "hello", "hi", "hey"]):
            return IntentResult(
                category=IntentCategory.CONVERSATION,
                capabilities_needed=[],
                confidence=0.90,
                raw_utterance=utterance
            )
            
        return IntentResult(
            category=IntentCategory.CONVERSATION,
            capabilities_needed=[],
            confidence=0.80,
            raw_utterance=utterance
        )
