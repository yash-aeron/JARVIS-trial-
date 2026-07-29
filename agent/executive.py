from typing import Dict, Any, Optional
from agent.decision_engine import DecisionEngine, AgentDecisionModel
from brain.intent_engine import IntentEngine, IntentResultModel
from state.state_manager import StateManager
from state.states import AssistantState
from core.interfaces import IEventBus, EventModel
from observability.logger import logger

class ExecutiveAgent:
    """Executive controller evaluating requests and emitting intent.detected events."""
    
    def __init__(self, intent_engine: IntentEngine, state_manager: StateManager, event_bus: Optional[IEventBus] = None):
        self.intent_engine = intent_engine
        self.decision_engine = DecisionEngine()
        self.state_manager = state_manager
        self.event_bus = event_bus

    async def process(self, utterance: str, correlation_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.state_manager.set_state(AssistantState.THINKING, "Executive Agent processing request", correlation_id=correlation_id)
        
        intent_res: IntentResultModel = await self.intent_engine.classify(utterance, correlation_id, context)
        decision: AgentDecisionModel = self.decision_engine.evaluate(utterance, intent_res.category.value, correlation_id)
        
        logger.info(f"Executive Decision [CID: {correlation_id}]: Intent={intent_res.category.value}, Decision={decision.model_dump()}")
        
        if self.event_bus:
            await self.event_bus.publish(
                EventModel(
                    correlation_id=correlation_id,
                    topic="intent.detected",
                    data={"utterance": utterance, "intent": intent_res.model_dump(), "decision": decision.model_dump()},
                    sender="ExecutiveAgent"
                )
            )
            
        return {
            "utterance": utterance,
            "correlation_id": correlation_id,
            "intent": intent_res,
            "decision": decision
        }
