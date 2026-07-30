import re
from typing import List, Optional
from core.models import PlanStepModel
from observability.logger import logger

_LAUNCH_VERBS = {"open", "launch", "kholo", "run", "start"}
_FILLER_WORDS = {"the", "a", "an", "my", "please", "up", "for", "me"}
_STATUS_WORDS = {"status", "cpu", "ram", "memory", "hardware", "performance", "usage"}
_SEARCH_VERBS = {"search", "google", "browse", "look"}
# Split on clause separators so "open chrome and check system status" becomes
# two steps instead of one bogus application named after the whole sentence.
_CLAUSE_SPLIT = re.compile(r"\s*(?:,|;|\bthen\b|\band then\b|\bafter that\b|\band\b)\s*")


class FallbackPlanner:
    """Isolated fallback planner for generating default capability steps when LLM inference is offline."""

    def generate_fallback_steps(self, goal: str) -> List[PlanStepModel]:
        logger.info(f"[FallbackPlanner] Generating fallback steps for goal: '{goal}'")

        clauses = [c.strip() for c in _CLAUSE_SPLIT.split(goal.lower()) if c.strip()]
        steps: List[PlanStepModel] = []

        for clause in clauses:
            step = self._step_for_clause(clause, next_id=len(steps) + 1)
            if step:
                steps.append(step)

        if not steps:
            steps.append(PlanStepModel(
                step_id=1,
                capability="system_control",
                args={"action": "get_status"},
                expected_observation="System status verified",
                depends_on=[]
            ))
        return steps

    def _step_for_clause(self, clause: str, next_id: int) -> Optional[PlanStepModel]:
        words = re.findall(r"[\w\-\+\.']+", clause)
        word_set = set(words)

        if word_set & _LAUNCH_VERBS:
            # Strip whole words only — substring replace turned "startup" into "up".
            app_words = [w for w in words if w not in _LAUNCH_VERBS and w not in _FILLER_WORDS]
            app_target = " ".join(app_words).strip()
            if not app_target:
                return None
            return PlanStepModel(
                step_id=next_id,
                capability="open_application",
                args={"app_name": app_target},
                expected_observation=f"Application '{app_target}' launched",
                depends_on=[]
            )

        if word_set & _STATUS_WORDS:
            return PlanStepModel(
                step_id=next_id,
                capability="system_control",
                args={"action": "get_status"},
                expected_observation="System status verified",
                depends_on=[]
            )

        if word_set & _SEARCH_VERBS:
            query_words = [w for w in words if w not in _SEARCH_VERBS and w not in _FILLER_WORDS]
            return PlanStepModel(
                step_id=next_id,
                capability="web_search",
                args={"query": " ".join(query_words).strip()},
                expected_observation="Search results retrieved",
                depends_on=[]
            )

        return None
