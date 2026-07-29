import uuid
import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from core.interfaces import ILLMProvider, IEventBus
from core.models import EventModel
from state.state_manager import StateManager
from state.states import AssistantState
from prompts.prompt_manager import PromptManager
from observability.logger import logger

class PlanStepModel(BaseModel):
    step_id: int
    capability: str
    args: Dict[str, Any] = Field(default_factory=dict)
    expected_observation: str
    depends_on: List[int] = Field(default_factory=list)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED

class ExecutionPlanModel(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str
    user_goal: str
    steps: List[PlanStepModel] = Field(default_factory=list)
    version: str = "1.0.0"

class Planner:
    """Multi-Step Planner generating capability-based ExecutionPlanModel via structured LLM prompting."""
    
    def __init__(self, llm: ILLMProvider, state_manager: StateManager, event_bus: Optional[IEventBus] = None):
        self.llm = llm
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.prompt_manager = PromptManager()

    async def create_plan(self, goal: str, capabilities_needed: List[str], correlation_id: str) -> ExecutionPlanModel:
        self.state_manager.set_state(AssistantState.PLANNING, f"Creating execution plan for: {goal}", correlation_id=correlation_id)
        logger.info(f"Generating capability-based plan [CID: {correlation_id}] for goal: '{goal}'")
        
        # 1. Fetch Markdown prompt via PromptManager
        prompt_text = self.prompt_manager.get("planner", goal=goal, capabilities=", ".join(capabilities_needed))
        
        # 2. Call LLM for structured JSON planning
        llm_json = await self.llm.generate_json(prompt=prompt_text, system_prompt="Output strict JSON execution plans.")
        
        steps: List[PlanStepModel] = []
        if isinstance(llm_json, dict) and "steps" in llm_json and isinstance(llm_json["steps"], list):
            for idx, raw_step in enumerate(llm_json["steps"], start=1):
                try:
                    steps.append(PlanStepModel(
                        step_id=raw_step.get("step_id", idx),
                        capability=raw_step.get("capability", "open_application"),
                        args=raw_step.get("args", {}),
                        expected_observation=raw_step.get("expected_observation", "Action executed"),
                        depends_on=raw_step.get("depends_on", [])
                    ))
                except Exception:
                    pass

        # Fallback parsing if LLM JSON is initializing or absent
        if not steps:
            goal_lower = goal.lower()
            if any(w in goal_lower for w in ["open", "launch", "kholo", "run", "start"]):
                app_target = goal_lower
                for prefix in ["open", "launch", "kholo", "run", "start", "jarvis"]:
                    app_target = app_target.replace(prefix, "").strip()
                if not app_target:
                    app_target = "notepad"
                    
                steps.append(PlanStepModel(
                    step_id=1,
                    capability="open_application",
                    args={"app_name": app_target},
                    expected_observation=f"Application '{app_target}' launched",
                    depends_on=[]
                ))
            else:
                steps.append(PlanStepModel(
                    step_id=1,
                    capability="system_control",
                    args={"action": "get_status"},
                    expected_observation="System status verified",
                    depends_on=[]
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
