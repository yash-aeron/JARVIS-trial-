import uuid
from typing import Dict, Any, List, Optional
from core.interfaces import ILLMProvider, IEventBus
from core.models import EventModel, PlanCreatedEventData, ExecutionPlanModel, PlanStepModel
from state.state_manager import StateManager
from state.states import AssistantState
from prompts.prompt_manager import PromptManager
from brain.plan_validator import PlanValidator
from brain.fallback_planner import FallbackPlanner
from observability.logger import logger

class Planner:
    """Multi-Step LLM-First Planner orchestrating prompt retrieval, LLM JSON generation, validation, and fallback."""
    
    def __init__(
        self, 
        llm: ILLMProvider, 
        state_manager: StateManager, 
        prompt_manager: PromptManager,
        event_bus: Optional[IEventBus] = None
    ):
        self.llm = llm
        self.state_manager = state_manager
        self.prompt_manager = prompt_manager
        self.event_bus = event_bus
        self.validator = PlanValidator()
        self.fallback_planner = FallbackPlanner()

    async def create_plan(self, goal: str, capabilities_needed: List[str], correlation_id: str) -> ExecutionPlanModel:
        self.state_manager.transition_to(AssistantState.PLANNING, f"Creating execution plan for: {goal}", correlation_id=correlation_id)
        logger.info(f"[Planner] Orchestrating capability plan [CID: {correlation_id}] for goal: '{goal}'")
        
        # 1. PromptManager injected via DI
        prompt_text = self.prompt_manager.get("planner", goal=goal, capabilities=", ".join(capabilities_needed))
        
        # 2. Structured JSON generation from LLM
        llm_json = await self.llm.generate_json(prompt=prompt_text, system_prompt="Output strict JSON execution plans.")
        
        # 3. Validation
        validated_plan = self.validator.validate_llm_json(llm_json, goal, correlation_id, available_capabilities=capabilities_needed)
        
        # 4. Fallback execution
        if not validated_plan or not validated_plan.steps:
            fallback_steps = self.fallback_planner.generate_fallback_steps(goal)
            validated_plan = ExecutionPlanModel(correlation_id=correlation_id, user_goal=goal, steps=fallback_steps)

        return validated_plan
