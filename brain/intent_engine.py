from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from core.interfaces import ILLMProvider
from core.models import ExecutionContextModel
from observability.logger import logger

class IntentCategory(str, Enum):
    CONVERSATION = "CONVERSATION"
    MULTI_STEP_PLAN = "MULTI_STEP_PLAN"
    SINGLE_TOOL = "SINGLE_TOOL"
    SYSTEM_CONTROL = "SYSTEM_CONTROL"
    QUERY_MEMORY = "QUERY_MEMORY"
    REJECT = "REJECT"

class IntentResultModel(BaseModel):
    category: IntentCategory
    capabilities_needed: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    raw_utterance: str
    correlation_id: str

class IntentEngine:
    """Classifies user utterances into actionable Pydantic IntentResultModel."""
    
    def __init__(self, llm_provider: ILLMProvider):
        self.llm = llm_provider

    async def classify(
        self, 
        utterance: str, 
        correlation_id: str, 
        context: Optional[ExecutionContextModel] = None
    ) -> IntentResultModel:
        text_lower = utterance.lower()
        
        # Capability-oriented intent matching
        if any(w in text_lower for w in ["open", "run", "launch", "kholo", "start"]):
            if any(w in text_lower for w in ["and", "then", "after", "search", "clone"]):
                return IntentResultModel(
                    category=IntentCategory.MULTI_STEP_PLAN,
                    capabilities_needed=["open_application", "web_search", "terminal_execution"],
                    confidence=0.95,
                    raw_utterance=utterance,
                    correlation_id=correlation_id
                )
            return IntentResultModel(
                category=IntentCategory.SINGLE_TOOL,
                capabilities_needed=["open_application"],
                confidence=0.90,
                raw_utterance=utterance,
                correlation_id=correlation_id
            )
            
        return IntentResultModel(
            category=IntentCategory.CONVERSATION,
            capabilities_needed=[],
            confidence=0.85,
            raw_utterance=utterance,
            correlation_id=correlation_id
        )
