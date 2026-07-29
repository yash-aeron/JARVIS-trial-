"""
tests/test_phase2.py — Unit and integration tests for Phase 2 Executive AI upgrades.
"""
import pytest
import asyncio
import uuid

from agent.decision_engine import DecisionEngine, AgentDecisionModel
from agent.executive import ExecutiveAgent, ExecutiveProcessResultModel
from brain.intent_engine import IntentEngine
from state.state_manager import StateManager
from context.context_manager import ContextSnapshotModel
from core.models import ToolResultModel


def test_decision_engine_subgoal_decomposition():
    """Test sub-goal decomposition for complex multi-action requests."""
    engine = DecisionEngine()

    single_goal = "Open notepad"
    assert engine.decompose_subgoals(single_goal) == ["Open notepad"]

    complex_goal = "Open Chrome and launch VS Code then check system status"
    subgoals = engine.decompose_subgoals(complex_goal)
    assert len(subgoals) == 3
    assert subgoals == ["Open Chrome", "launch VS Code", "check system status"]


def test_decision_engine_constraint_reasoning():
    """Test policy constraint evaluation against risk levels and operating mode rules."""
    engine = DecisionEngine()

    # Risk CRITICAL constraint check
    is_allowed, violations = engine.evaluate_constraints(
        capabilities_needed=["system_control"],
        risk_level="CRITICAL"
    )
    assert is_allowed is False
    assert len(violations) == 1
    assert "CRITICAL" in violations[0]

    # Gaming mode application launch restriction check
    context = ContextSnapshotModel(active_mode="Gaming")
    is_allowed, violations = engine.evaluate_constraints(
        capabilities_needed=["open_application"],
        risk_level="LOW",
        context=context
    )
    assert is_allowed is False
    assert "Gaming mode" in violations[0]


@pytest.mark.asyncio
async def test_executive_agent_reflection_loop():
    """Test ExecutiveAgent reflection evaluation on goal execution results."""
    sm = StateManager()
    intent_eng = IntentEngine(llm_provider=None)
    exec_agent = ExecutiveAgent(intent_engine=intent_eng, state_manager=sm)

    res_success = [
        ToolResultModel(request_id="step_1", correlation_id="cid_1", status="completed", result={"output": "ok"})
    ]
    assert exec_agent.reflect("Open notepad", res_success) is True

    res_failed = [
        ToolResultModel(request_id="step_1", correlation_id="cid_1", status="failed", error="App missing")
    ]
    assert exec_agent.reflect("Open invalid app", res_failed) is False
