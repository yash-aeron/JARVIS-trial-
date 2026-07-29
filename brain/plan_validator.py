from typing import Dict, Any, List, Optional
from pydantic import ValidationError
from core.models import ExecutionPlanModel, PlanStepModel
from observability.logger import logger

class PlanValidator:
    """Validates raw LLM JSON responses into strongly-typed Pydantic ExecutionPlanModel structures without silent error swallowing."""
    
    @staticmethod
    def validate_llm_json(llm_json: Any, goal: str, correlation_id: str) -> Optional[ExecutionPlanModel]:
        if not isinstance(llm_json, dict) or "steps" not in llm_json or not isinstance(llm_json["steps"], list):
            logger.warning(f"[PlanValidator] Raw LLM JSON is not a valid plan dict: {llm_json}")
            return None
            
        steps: List[PlanStepModel] = []
        for idx, raw_step in enumerate(llm_json["steps"], start=1):
            try:
                step_obj = PlanStepModel(
                    step_id=raw_step.get("step_id", idx),
                    capability=raw_step.get("capability", "open_application"),
                    args=raw_step.get("args", {}),
                    expected_observation=raw_step.get("expected_observation", "Step completed"),
                    depends_on=raw_step.get("depends_on", [])
                )
                steps.append(step_obj)
            except ValidationError as e:
                logger.warning(f"[PlanValidator] Validation error on step {idx}: {e}")
            except Exception as e:
                logger.error(f"[PlanValidator] Unexpected error parsing step {idx}: {e}")
                
        if steps:
            return ExecutionPlanModel(correlation_id=correlation_id, user_goal=goal, steps=steps)
        return None
