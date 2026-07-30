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
                capability = str(
                    raw_step.get("capability")
                    or raw_step.get("tool")
                    or raw_step.get("tool_name")
                    or "open_application"
                )

                # Check capability availability
                if available_capabilities and capability not in available_capabilities:
                    logger.warning(f"[PlanValidator] Capability '{capability}' is not registered in ToolRegistry.")

                args_dict = PlanValidator._coerce_args(raw_step.get("args"), capability)

                raw_deps = raw_step.get("depends_on", raw_step.get("dependencies", []))
                deps_list = [d for d in raw_deps if isinstance(d, int)] if isinstance(raw_deps, list) else []

                observation = (
                    raw_step.get("expected_observation")
                    or raw_step.get("observation")
                    or "Step completed"
                )

                step_obj = PlanStepModel(
                    step_id=step_id,
                    capability=capability,
                    args=args_dict,
                    expected_observation=str(observation),
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

        PlanValidator._break_cycles(steps)

        if steps:
            return ExecutionPlanModel(correlation_id=correlation_id, user_goal=goal, steps=steps)
        return None

    @staticmethod
    def _coerce_args(raw_args: Any, capability: str) -> Dict[str, Any]:
        """
        Normalize the many arg shapes models emit into the dict tools expect.

        Models frequently return a bare string ("chrome") or an alternate key
        ("application"), both of which tools would silently ignore.
        """
        key_aliases = {
            "application": "app_name",
            "app": "app_name",
            "program": "app_name",
            "name": "app_name",
            "search_query": "query",
            "q": "query",
        }

        if isinstance(raw_args, dict):
            normalized: Dict[str, Any] = {}
            for k, v in raw_args.items():
                normalized[key_aliases.get(str(k).lower(), str(k))] = v
            return normalized

        if isinstance(raw_args, str) and raw_args.strip():
            value = raw_args.strip()
            if capability in ("web_search", "search"):
                return {"query": value}
            if capability == "system_control":
                return {"action": value}
            return {"app_name": value}

        return {}

    @staticmethod
    def _break_cycles(steps: List[PlanStepModel]) -> None:
        """
        Remove dependency edges that form cycles.

        A cycle would otherwise leave every step permanently unready, and the
        executor fails the whole plan with "unsatisfied dependency".
        """
        by_id = {s.step_id: s for s in steps}
        # 0 = unvisited, 1 = in progress on this DFS path, 2 = fully explored
        state: Dict[int, int] = {sid: 0 for sid in by_id}

        def visit(sid: int) -> None:
            state[sid] = 1
            step = by_id[sid]
            kept: List[int] = []
            for dep in step.depends_on:
                if dep not in by_id:
                    continue
                if state[dep] == 1:
                    logger.warning(
                        f"[PlanValidator] Circular dependency detected: step {sid} -> {dep}. Dropping edge."
                    )
                    continue
                if state[dep] == 0:
                    visit(dep)
                kept.append(dep)
            step.depends_on = kept
            state[sid] = 2

        for sid in list(by_id):
            if state[sid] == 0:
                visit(sid)
