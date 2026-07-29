from typing import Dict, Any, List
from observability.logger import logger

class QualityEvaluator:
    """Evaluates assistant quality across tool selection accuracy, plan optimality, and memory retrieval precision."""
    
    def evaluate_tool_selection(self, predicted_tool: str, expected_tool: str) -> Dict[str, Any]:
        match = (predicted_tool == expected_tool)
        logger.info(f"[QualityEvaluator] Tool Selection Evaluation: predicted='{predicted_tool}', expected='{expected_tool}', match={match}")
        return {"metric": "tool_selection_accuracy", "pass": match, "score": 1.0 if match else 0.0}

    def evaluate_plan_optimality(self, plan_steps_count: int, expected_max_steps: int) -> Dict[str, Any]:
        optimal = plan_steps_count <= expected_max_steps
        logger.info(f"[QualityEvaluator] Plan Optimality Evaluation: steps={plan_steps_count}, max_expected={expected_max_steps}, optimal={optimal}")
        return {"metric": "plan_optimality", "pass": optimal, "score": 1.0 if optimal else 0.5}
