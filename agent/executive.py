from typing import Optional, Any
from pydantic import BaseModel
from agent.decision_engine import DecisionEngine, AgentDecisionModel
from brain.intent_engine import IntentEngine, IntentResultModel
from state.state_manager import StateManager
from state.states import AssistantState
from core.interfaces import IEventBus
from core.models import EventModel, IntentDetectedEventData, ExecutionContextModel
from observability.logger import logger

class ExecutiveProcessResultModel(BaseModel):
    utterance: str
    correlation_id: str
    intent: IntentResultModel
    decision: AgentDecisionModel

class ExecutiveAgent:
    """Executive controller orchestrating subagents and emitting typed IntentDetectedEventData payloads over AsyncEventBus."""

    def __init__(
        self, 
        intent_engine: IntentEngine, 
        state_manager: StateManager, 
        event_bus: Optional[IEventBus] = None,
        planning_subagent: Optional[Any] = None,
        memory_subagent: Optional[Any] = None,
        execution_subagent: Optional[Any] = None
    ):
        self.intent_engine = intent_engine
        self.decision_engine = DecisionEngine()
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.planning_subagent = planning_subagent
        self.memory_subagent = memory_subagent
        self.execution_subagent = execution_subagent

    async def process(
        self, 
        utterance: str, 
        correlation_id: str, 
        context: Optional[ExecutionContextModel] = None
    ) -> ExecutiveProcessResultModel:
        self.state_manager.transition_to(AssistantState.THINKING, "Executive Agent processing request", correlation_id=correlation_id)

        intent_res: IntentResultModel = await self.intent_engine.classify(utterance, correlation_id, context)
        decision: AgentDecisionModel = self.decision_engine.evaluate(
            utterance=utterance,
            intent_category=intent_res.category.value,
            correlation_id=correlation_id,
            capabilities_needed=intent_res.capabilities_needed,
            context=context
        )

        logger.info(f"Executive Decision [CID: {correlation_id}]: Confidence={decision.confidence:.2f}, Risk={decision.risk_level}, Allowed={decision.is_allowed}, Intent={intent_res.category.value}")

        if self.event_bus:
            payload = IntentDetectedEventData(
                utterance=utterance,
                intent_category=intent_res.category.value,
                confidence=decision.confidence,
                risk_level=decision.risk_level
            )
            await self.event_bus.publish(
                EventModel(
                    correlation_id=correlation_id,
                    topic="intent.detected",
                    payload=payload,
                    sender="ExecutiveAgent"
                )
            )

        return ExecutiveProcessResultModel(
            utterance=utterance,
            correlation_id=correlation_id,
            intent=intent_res,
            decision=decision
        )

    def reflect(self, user_goal: str, execution_results: list) -> bool:
        """Reflection loop: Evaluate whether user goal was actually satisfied by execution results."""
        if not execution_results:
            logger.warning(f"[ExecutiveReflection] Goal '{user_goal}' yielded no execution results.")
            return False

        all_completed = all(getattr(r, "status", "") == "completed" for r in execution_results)
        if not all_completed:
            logger.warning(f"[ExecutiveReflection] Goal '{user_goal}' has incomplete or failed step executions.")
            return False

        logger.info(f"[ExecutiveReflection] Goal '{user_goal}' successfully satisfied.")
        return True
