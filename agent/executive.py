from typing import Dict, Any, Optional
from agent.decision_engine import DecisionEngine, ExecutiveDecision
from brain.intent_engine import IntentEngine, IntentCategory
from state.state_manager import StateManager
from state.states import AssistantState
from observability.logger import logger

class ExecutiveAgent:
    """Executive controller directing utterance flow through intent classification, decision making, and strategy selection."""
    
    def __init__(self, intent_engine: IntentEngine, state_manager: StateManager):
        self.intent_engine = intent_engine
        self.decision_engine = DecisionEngine()
        self.state_manager = state_manager

    async def process(self, utterance: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.state_manager.set_state(AssistantState.THINKING, "Executive Agent processing utterance")
        
        intent_res = await self.intent_engine.classify(utterance, context)
        decision = self.decision_engine.evaluate(utterance, intent_res.category.name)
        
        logger.info(f"Executive Decision for '{utterance}': Intent={intent_res.category.name}, Decision={decision}")
        
        return {
            "utterance": utterance,
            "intent": intent_res,
            "decision": decision
        }
