from typing import Dict, List, Set
from core.models import ExecutionPlanModel, PlanStepModel
from observability.logger import logger

class PlanOptimizer:
    """Optimizes ExecutionPlanModel by removing duplicate capability steps, eliminating redundant steps, and ordering step dependencies."""
    
    def optimize(self, plan: ExecutionPlanModel) -> ExecutionPlanModel:
        if not plan.steps:
            return plan
            
        logger.info(f"[PlanOptimizer] Optimizing plan '{plan.plan_id}' ({len(plan.steps)} initial steps)")
        
        # 1. Eliminate Duplicate Capability & Arguments Steps
        unique_steps: List[PlanStepModel] = []
        signature_owner: Dict[str, int] = {}
        # A dependency on a removed duplicate must point at the surviving twin,
        # not be dropped — otherwise ordered steps start running concurrently.
        canonical_id: Dict[int, int] = {}

        for step in plan.steps:
            sig = f"{step.capability}:{str(step.args)}"
            if sig not in signature_owner:
                signature_owner[sig] = step.step_id
                canonical_id[step.step_id] = step.step_id
                unique_steps.append(step)
            else:
                canonical_id[step.step_id] = signature_owner[sig]
                logger.info(f"[PlanOptimizer] Removed duplicate step {step.step_id} ({sig})")

        # 2. Re-index step IDs and preserve valid dependency IDs
        id_mapping = {old_step.step_id: new_id for new_id, old_step in enumerate(unique_steps, start=1)}

        optimized_steps: List[PlanStepModel] = []
        for new_id, step in enumerate(unique_steps, start=1):
            valid_deps = []
            for dep in step.depends_on:
                survivor = canonical_id.get(dep)
                if survivor is None:
                    logger.debug(f"[PlanOptimizer] Pruned unknown dependency {dep} from step {step.step_id}")
                    continue
                mapped = id_mapping.get(survivor)
                if mapped is None or mapped == new_id:
                    continue
                if mapped not in valid_deps:
                    valid_deps.append(mapped)
            optimized_steps.append(
                PlanStepModel(
                    step_id=new_id,
                    capability=step.capability,
                    args=step.args,
                    expected_observation=step.expected_observation,
                    depends_on=valid_deps,
                    status=step.status
                )
            )
            
        logger.info(f"[PlanOptimizer] Optimization complete ({len(optimized_steps)} final steps)")
        return ExecutionPlanModel(
            plan_id=plan.plan_id,
            correlation_id=plan.correlation_id,
            user_goal=plan.user_goal,
            steps=optimized_steps,
            version=plan.version
        )
