import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from core.interfaces import ILLMProvider, IEventBus, EventModel
from state.state_manager import StateManager
from state.states import AssistantState
from observability.logger import logger

class PlanStepModel(BaseModel):
    step_id: int
    capability: str
    args: Dict[str, Any] = Field(default_factory=dict)
    expected_observation: str
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED

class ExecutionPlanModel(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str
    user_goal: str
    steps: List[PlanStepModel] = Field(default_factory=list)
    version: str = "1.0.0"

class Planner:
    """Multi-Step Planner generating Pydantic ExecutionPlanModel based on capabilities."""
    
    def __init__(self, llm: ILLMProvider, state_manager: StateManager, event_bus: Optional[IEventBus] = None):
        self.llm = llm
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.prompt_path = Path(__file__).parent.parent / "prompts" / "planner.md"

    async def create_plan(self, goal: str, capabilities_needed: List[str], correlation_id: str) -> ExecutionPlanModel:
        self.state_manager.set_state(AssistantState.PLANNING, f"Creating execution plan for: {goal}", correlation_id=correlation_id)
        logger.info(f"Generating capability-based plan [CID: {correlation_id}] for goal: '{goal}'")
        
        # Load external Markdown prompt template
        template_text = ""
        if self.prompt_path.exists():
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                template_text = f.read()
                
        steps: List[PlanStepModel] = []
        goal_lower = goal.lower()
        
        if any(w in goal_lower for w in ["open", "launch", "kholo", "run", "start"]):
            # Extract target application name
            app_target = goal_lower
            for prefix in ["open", "launch", "kholo", "run", "start", "jarvis"]:
                app_target = app_target.replace(prefix, "").strip()
            if not app_target:
                app_target = "notepad"
                
            steps.append(PlanStepModel(
                step_id=1,
                capability="open_application",
                args={"app_name": app_target},
                expected_observation=f"Application '{app_target}' launched"
            ))
        else:
            steps.append(PlanStepModel(
                step_id=1,
                capability="system_control",
                args={"action": "get_status"},
                expected_observation="System status verified"
            ))

        plan = ExecutionPlanModel(correlation_id=correlation_id, user_goal=goal, steps=steps)
        
        if self.event_bus:
            await self.event_bus.publish(
                EventModel(
                    correlation_id=correlation_id,
                    topic="plan.created",
                    data={"plan": plan.model_dump()},
                    sender="Planner"
                )
            )
            
        return plan
