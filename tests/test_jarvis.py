import pytest
import asyncio
import uuid

from core.container import DependencyContainer
from core.app import JARVISApp, bootstrap_container
from core.models import EventModel, ToolRequestModel, ToolResultModel
from core.event_bus import AsyncEventBus
from state.state_manager import StateManager
from state.states import AssistantState, StateTransitionError
from tools.registry import ToolRegistry
from tools.system_tools import ApplicationLauncherTool
from brain.planner import Planner, ExecutionPlanModel, PlanStepModel
from automation.executor import PlanExecutor
from automation.undo_manager import UndoManager

def test_bootstrap_container_auto_wiring():
    container = bootstrap_container()
    app = JARVISApp(container)
    assert app.container is container
    
    resolved_app = container.resolve(JARVISApp)
    assert resolved_app is app

def test_guarded_illegal_state_transition():
    sm = StateManager()
    sm.set_state(AssistantState.LISTENING, "Listening to user")
    
    # Illegal jump LISTENING -> PLANNING (Must go LISTENING -> THINKING -> PLANNING)
    with pytest.raises(StateTransitionError):
        sm.set_state(AssistantState.PLANNING, "Direct jump forbidden")

def test_runtime_context_tool_ranking():
    registry = ToolRegistry()
    tool = ApplicationLauncherTool()
    registry.register(tool)
    
    context = {"focused_app": "VS Code", "active_mode": "Developer"}
    ranked = registry.find_and_rank_by_capability("open_application", context=context)
    assert len(ranked) >= 1
    selected_tool, score = ranked[0]
    assert selected_tool.metadata.name == "app_launcher"
    assert score > 0.8

@pytest.mark.asyncio
async def test_parallel_dependency_aware_executor():
    registry = ToolRegistry()
    tool = ApplicationLauncherTool()
    registry.register(tool)
    
    undo_mgr = UndoManager()
    state_mgr = StateManager()
    executor = PlanExecutor(registry, undo_mgr, state_mgr)
    cid = str(uuid.uuid4())
    
    # Two independent steps with depends_on=[] intended for parallel execution
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
