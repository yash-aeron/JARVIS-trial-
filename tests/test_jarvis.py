import pytest
import asyncio
import uuid

from core.container import DependencyContainer
from core.app import JARVISApp, bootstrap_container
from core.interfaces import IEventBus
from core.models import EventModel, ToolRequestModel, ToolResultModel
from core.event_bus import AsyncEventBus
from state.state_manager import StateManager
from state.states import AssistantState, StateTransitionError
from tools.registry import ToolRegistry
from tools.system_tools import ApplicationLauncherTool
from brain.planner import Planner, ExecutionPlanModel, PlanStepModel
from brain.plan_validator import PlanValidator
from brain.fallback_planner import FallbackPlanner
from automation.executor import PlanExecutor
from automation.undo_manager import UndoManager
from memory.schema import MemoryItemModel
from memory.memory_manager import MemoryManager

def test_strict_class_key_dependency_injection():
    container = bootstrap_container()
    app = JARVISApp(container)
    
    # Assert resolving by Class/Interface type works cleanly
    resolved_bus = container.resolve(IEventBus)
    assert isinstance(resolved_bus, AsyncEventBus)
    
    resolved_app = container.resolve(JARVISApp)
    assert resolved_app is app

def test_guarded_state_machine_transitions():
    sm = StateManager()
    sm.transition_to(AssistantState.LISTENING, "User speaking")
    assert sm.current_state == AssistantState.LISTENING
    
    # Attempt illegal transition directly from LISTENING -> PLANNING
    with pytest.raises(StateTransitionError):
        sm.transition_to(AssistantState.PLANNING, "Direct jump forbidden")

def test_plan_validator_without_silent_swallowing():
    validator = PlanValidator()
    
    # Test valid JSON schema parsing
    valid_json = {
        "steps": [
            {"step_id": 1, "capability": "open_application", "args": {"app_name": "notepad"}, "expected_observation": "Notepad opened"}
        ]
    }
    plan = validator.validate_llm_json(valid_json, "Open Notepad", "cid_123")
    assert plan is not None
    assert len(plan.steps) == 1
    assert plan.steps[0].capability == "open_application"

def test_memory_retrieval_ranking():
    mem_mgr = MemoryManager(db_path="data/test_ranked_memory.db")
    item1 = MemoryItemModel(content="User prefers dark theme", tags=["preference", "theme"], importance=4.5)
    item2 = MemoryItemModel(content="User bought groceries", tags=["personal", "shopping"], importance=1.0)
    
    mem_mgr.store(item1)
    mem_mgr.store(item2)
    
    ranked = mem_mgr.query_and_rank(query_tags=["preference"])
    assert len(ranked) >= 1
    top_item, score = ranked[0]
    assert top_item.content == "User prefers dark theme"
    assert score > 3.0

@pytest.mark.asyncio
async def test_parallel_dependency_aware_executor():
    registry = ToolRegistry()
    tool = ApplicationLauncherTool()
    registry.register(tool)
    
    undo_mgr = UndoManager()
    state_mgr = StateManager()
    executor = PlanExecutor(registry, undo_mgr, state_mgr)
    cid = str(uuid.uuid4())
    
    plan = ExecutionPlanModel(
        correlation_id=cid,
        user_goal="Open apps concurrently",
        steps=[
            PlanStepModel(step_id=1, capability="open_application", args={"app_name": "notepad"}, expected_observation="Notepad", depends_on=[]),
            PlanStepModel(step_id=2, capability="open_application", args={"app_name": "notepad"}, expected_observation="Notepad 2", depends_on=[])
        ]
    )
    
    results = await executor.execute_plan(plan)
    assert len(results) == 2
    assert all(r.status == "completed" for r in results)

@pytest.mark.asyncio
async def test_full_end_to_end_pipeline():
    app = JARVISApp()
    await app.initialize()
    
    res = await app.process_user_command("Open notepad")
    assert "correlation_id" in res
    assert res["intent"] in ["SINGLE_TOOL", "MULTI_STEP_PLAN"]
    assert len(res["execution_results"]) >= 1
    assert res["execution_results"][0]["status"] == "completed"
    
    await app.shutdown()
