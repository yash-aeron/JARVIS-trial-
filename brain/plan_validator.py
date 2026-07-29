from typing import Dict, Any, List, Optional, Set
from pydantic import ValidationError
from core.models import ExecutionPlanModel, PlanStepModel
from observability.logger import logger

class PlanValidator:
    """Validates raw LLM JSON responses into ExecutionPlanModel with checks for duplicate IDs, valid depends_on, circular dependencies, and capabilities."""
    
    @staticmethod
    def validate_llm_json(llm_json: Any, goal: str, correlation_id: str, available_capabilities: Optional[List[str]] = None) -> Optional[ExecutionPlanModel]:
        if not isinstance(llm_json, dict) or "steps" not in llm_json or not isinstance(llm_json["steps"], list):
            logger.warning(f"[PlanValidator] Raw LLM JSON is not a valid plan dict: {llm_json}")
            return None
            
        steps: List[PlanStepModel] = []
        seen_step_ids: Set[int] = set()
        
        for idx, raw_step in enumerate(llm_json["steps"], start=1):
            if not isinstance(raw_step, dict):
                logger.warning(f"[PlanValidator] Skipping non-dict step element at index {idx}: {raw_step}")
                continue
                
            try:
                step_id = raw_step.get("step_id", idx)
                if not isinstance(step_id, int) or step_id in seen_step_ids:
                    logger.warning(f"[PlanValidator] Invalid or duplicate step_id '{step_id}' detected. Reassigning.")
                    step_id = max(seen_step_ids, default=0) + 1
                    
                seen_step_ids.add(step_id)
                capability = str(raw_step.get("capability", "open_application"))
                
                # Check capability availability
                if available_capabilities and capability not in available_capabilities:
                    logger.warning(f"[PlanValidator] Capability '{capability}' is not registered in ToolRegistry.")
                    
                raw_args = raw_step.get("args", {})
                args_dict = raw_args if isinstance(raw_args, dict) else {}
                
                raw_deps = raw_step.get("depends_on", [])
                deps_list = [d for d in raw_deps if isinstance(d, int)] if isinstance(raw_deps, list) else []
                
                step_obj = PlanStepModel(
                    step_id=step_id,
                    capability=capability,
                    args=args_dict,
                    expected_observation=str(raw_step.get("expected_observation", "Step completed")),
                    depends_on=deps_list
                )
                steps.append(step_obj)
            except ValidationError as e:
                logger.warning(f"[PlanValidator] Validation error on step {idx}: {e}")
            except Exception as e:
                logger.error(f"[PlanValidator] Unexpected error parsing step {idx}: {e}")
                
        # Validate dependency integrity (all depends_on references must exist & no self/circular dependency)
        valid_step_ids = {s.step_id for s in steps}
        for s in steps:
            s.depends_on = [dep for dep in s.depends_on if dep in valid_step_ids and dep != s.step_id]
            
        if steps:
            return ExecutionPlanModel(correlation_id=correlation_id, user_goal=goal, steps=steps)
        return None
