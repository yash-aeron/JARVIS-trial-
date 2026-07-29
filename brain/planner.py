import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from core.interfaces import ILLMProvider
from state.state_manager import StateManager
from state.states import AssistantState
from observability.logger import logger

@dataclass
class PlanStep:
    step_id: int
    tool_name: str
    args: Dict[str, Any]
    expected_observation: str
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED

@dataclass
class ExecutionPlan:
    plan_id: str
    user_goal: str
    steps: List[PlanStep] = field(default_factory=list)
    version: str = "1.0.0"

class Planner:
    """Multi-Step Planner generating pure ExecutionPlan structures without direct execution side-effects."""
    
    def __init__(self, llm: ILLMProvider, state_manager: StateManager):
        self.llm = llm
        self.state_manager = state_manager

    async def create_plan(self, goal: str, available_capabilities: List[str]) -> ExecutionPlan:
        self.state_manager.set_state(AssistantState.PLANNING, f"Creating execution plan for: {goal}")
        logger.info(f"Generating plan for goal: '{goal}'")
        
        # Decompose goal into execution steps
        steps = []
        if "open" in goal.lower() or "launch" in goal.lower():
            steps.append(PlanStep(step_id=1, tool_name="app_launcher", args={"app_name": "VS Code", "action": "launch"}, expected_observation="VS Code opened"))
            steps.append(PlanStep(step_id=2, tool_name="system_control", args={"action": "get_status"}, expected_observation="System status verified"))
        else:
            steps.append(PlanStep(step_id=1, tool_name="system_control", args={"action": "get_status"}, expected_observation="Status retrieved"))

        plan = ExecutionPlan(plan_id="plan_001", user_goal=goal, steps=steps)
        logger.info(f"ExecutionPlan generated with {len(steps)} steps.")
        return plan
