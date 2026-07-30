import re
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

    @staticmethod
    def _capabilities_for(words: set) -> List[str]:
        """
        Derive the capabilities a multi-step goal actually needs.

        Offering every capability unconditionally invited the planner to invent
        unrelated steps (e.g. a shell command for a CPU reading).
        """
        caps = ["open_application"]
        if words & {"search", "google", "browse", "news", "weather", "lookup"}:
            caps.append("web_search")
        if words & {"status", "cpu", "ram", "memory", "hardware", "performance", "usage", "battery"}:
            caps.append("system_control")
        if words & {"clone", "git", "npm", "pip", "terminal", "command", "shell"}:
            caps.append("terminal_execution")
        if words & {"remember", "notes", "preference", "history"}:
            caps.append("recall_memory")
        return caps

    async def classify(
        self,
        utterance: str,
        correlation_id: str,
        context: Optional[ExecutionContextModel] = None
    ) -> IntentResultModel:
        # Whole-word matching: substring checks made "run" fire on "brunch" and
        # launch an application for unrelated utterances.
        words = set(re.findall(r"[a-z0-9\-']+", utterance.lower()))

        # Capability-oriented intent matching
        if words & {"open", "run", "launch", "kholo", "start"}:
            if words & {"and", "then", "after", "search", "clone"}:
                return IntentResultModel(
                    category=IntentCategory.MULTI_STEP_PLAN,
                    capabilities_needed=self._capabilities_for(words),
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

        if words & {"status", "cpu", "ram", "memory", "hardware", "performance", "usage", "battery"}:
            return IntentResultModel(
                category=IntentCategory.SYSTEM_CONTROL,
                capabilities_needed=["system_control"],
                confidence=0.85,
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
