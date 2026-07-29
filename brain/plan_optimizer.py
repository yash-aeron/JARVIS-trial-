from typing import List, Set
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
        seen_signatures: Set[str] = set()
        
        for step in plan.steps:
            sig = f"{step.capability}:{str(step.args)}"
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                unique_steps.append(step)
            else:
                logger.info(f"[PlanOptimizer] Removed duplicate step {step.step_id} ({sig})")
                
        # 2. Re-index step IDs and preserve valid dependency IDs
        id_mapping = {old_step.step_id: new_id for new_id, old_step in enumerate(unique_steps, start=1)}
        
        optimized_steps: List[PlanStepModel] = []
        for new_id, step in enumerate(unique_steps, start=1):
            valid_deps = []
            for dep in step.depends_on:
                if dep in id_mapping and dep != step.step_id:
                    valid_deps.append(id_mapping[dep])
                else:
                    logger.debug(f"[PlanOptimizer] Pruned dependency link {dep} from step {step.step_id}")
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
