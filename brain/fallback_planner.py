from typing import List
from core.models import PlanStepModel
from observability.logger import logger

class FallbackPlanner:
    """Isolated fallback planner for generating default capability steps when LLM inference is offline."""
    
    def generate_fallback_steps(self, goal: str) -> List[PlanStepModel]:
        logger.info(f"[FallbackPlanner] Generating fallback steps for goal: '{goal}'")
        steps: List[PlanStepModel] = []
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
        return steps
