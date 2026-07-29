from core.models import ToolSelectionEvalModel, PlanOptimalityEvalModel
from observability.logger import logger

class QualityEvaluator:
    """Evaluates assistant decision quality and plan optimality."""
    
    def evaluate_tool_selection(self, predicted_tool: str, expected_tool: str) -> ToolSelectionEvalModel:
        match = predicted_tool.lower() == expected_tool.lower()
        logger.info(f"[QualityEvaluator] Tool Selection Evaluation: predicted='{predicted_tool}', expected='{expected_tool}', match={match}")
        return ToolSelectionEvalModel(
            predicted_tool=predicted_tool,
            expected_tool=expected_tool,
            match=match
        )

    def evaluate_plan_optimality(self, plan_steps_count: int, expected_max_steps: int) -> PlanOptimalityEvalModel:
        optimal = plan_steps_count <= expected_max_steps
        logger.info(f"[QualityEvaluator] Plan Optimality Evaluation: steps={plan_steps_count}, max_expected={expected_max_steps}, optimal={optimal}")
        return PlanOptimalityEvalModel(
            steps=plan_steps_count,
            max_expected=expected_max_steps,
            optimal=optimal
        )
