import re
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field
from core.models import ExecutionContextModel

class AgentDecisionModel(BaseModel):
    correlation_id: str
    confidence: float = 0.90
    needs_planning: bool
    needs_memory: bool
    needs_vision: bool
    needs_web: bool
    needs_clarification: bool
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    clarification_prompt: Optional[str] = None
    subgoals: List[str] = Field(default_factory=list)
    constraint_violations: List[str] = Field(default_factory=list)
    is_allowed: bool = True

class DecisionEngine:
    """Executive decision engine assessing request scope, sub-goal decomposition, constraints, confidence, risk levels, and clarification needs."""

    def decompose_subgoals(self, utterance: str) -> List[str]:
        """Break down complex multi-action user requests into ordered sub-goals."""
        text_lower = utterance.lower()
        if " and " in text_lower or " then " in text_lower or " also " in text_lower:
            delimiters = [" and ", " then ", " also ", ", "]
            parts = [utterance]
            for delim in delimiters:
                new_parts = []
                for p in parts:
                    new_parts.extend(p.split(delim))
                parts = new_parts
            cleaned = [p.strip() for p in parts if p.strip()]
            return cleaned if len(cleaned) > 1 else [utterance]
        return [utterance]

    def evaluate_constraints(
        self,
        capabilities_needed: List[str],
        risk_level: str,
        context: Optional[ExecutionContextModel] = None
    ) -> Tuple[bool, List[str]]:
        """Evaluate resource, permission, and operating mode constraints before planning."""
        violations = []
        if risk_level == "CRITICAL":
            violations.append("Action risk level is CRITICAL; explicit user confirmation required.")

        if context and hasattr(context, "active_mode"):
            mode = getattr(context, "active_mode", "")
            # Example mode restriction enforcement
            if mode == "Gaming" and any(c in capabilities_needed for c in ["open_application", "app_automation"]):
                violations.append("Application launching is restricted while in Gaming mode.")

        is_allowed = len(violations) == 0
        return is_allowed, violations

    def evaluate(
        self,
        utterance: str,
        intent_category: str,
        correlation_id: str,
        capabilities_needed: Optional[List[str]] = None,
        context: Optional[ExecutionContextModel] = None
    ) -> AgentDecisionModel:
        text_lower = utterance.lower()
        words = set(re.findall(r"[a-z0-9\-']+", text_lower))

        needs_planning = (intent_category == "MULTI_STEP_PLAN")
        needs_memory = bool(words & {"remember", "history", "notes", "preference", "preferences"}) or \
            any(p in text_lower for p in ["last time", "my preference"])
        needs_vision = bool(words & {"screen", "see", "look", "window", "ocr", "screenshot"})
        needs_web = bool(words & {"weather", "news", "search", "download", "browse"})

        risk_level = "LOW"
        if bool(words & {"delete", "shutdown", "format", "wipe"}) or "rm -rf" in text_lower:
            risk_level = "CRITICAL"
        elif bool(words & {"install", "update", "write"}) or "git push" in text_lower:
            risk_level = "MEDIUM"

        # Match whole words: substring matching made "hi" fire on "which" and
        # "run" on "brunch", misrouting unrelated utterances into app launches.
        confidence = 0.95 if words & {"open", "launch", "kholo", "run", "start", "hello", "hi"} else 0.40
        # Don't demand clarification when we already know what the request needs.
        has_actionable_signal = bool(capabilities_needed) or needs_planning or needs_memory or needs_vision or needs_web
        needs_clarification = (confidence < 0.50) and not has_actionable_signal

        subgoals = self.decompose_subgoals(utterance) if needs_planning else [utterance]
        is_allowed, violations = self.evaluate_constraints(
            capabilities_needed or [],
            risk_level,
            context
        )

        clarification_prompt = "Could you please clarify your request?" if needs_clarification else None
        if not is_allowed and violations:
            needs_clarification = True
            clarification_prompt = f"Action blocked by policy constraint: {violations[0]}"

        return AgentDecisionModel(
            correlation_id=correlation_id,
            confidence=confidence,
            needs_planning=needs_planning,
            needs_memory=needs_memory,
            needs_vision=needs_vision,
            needs_web=needs_web,
            needs_clarification=needs_clarification,
            risk_level=risk_level,
            clarification_prompt=clarification_prompt,
            subgoals=subgoals,
            constraint_violations=violations,
            is_allowed=is_allowed
        )
