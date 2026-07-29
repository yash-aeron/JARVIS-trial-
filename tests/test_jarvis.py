import pytest
import asyncio
import uuid

from core.container import DependencyContainer
from core.models import EventModel, ToolRequestModel, ToolResultModel
from core.event_bus import AsyncEventBus
from state.state_manager import StateManager
from state.states import AssistantState, StateTransitionError
from language.detector import CodeSwitchLanguageDetector
from tools.registry import ToolRegistry
from tools.system_tools import ApplicationLauncherTool
from brain.planner import Planner, ExecutionPlanModel, PlanStepModel
from brain.intent_engine import IntentEngine
from agent.executive import ExecutiveAgent
from automation.executor import PlanExecutor
from automation.undo_manager import UndoManager
from prompts.prompt_manager import PromptManager

def test_type_based_dependency_injection():
    container = DependencyContainer()
    bus = AsyncEventBus()
    container.register_singleton(AsyncEventBus, bus)
    
    resolved = container.resolve(AsyncEventBus)
    assert resolved is bus

def test_guarded_state_machine_transitions():
    sm = StateManager()
    assert sm.current_state == AssistantState.IDLE
    sm.set_state(AssistantState.LISTENING, "User speaking")
    assert sm.current_state == AssistantState.LISTENING
    
    # Attempt invalid transition directly from LISTENING -> PLANNING
    with pytest.raises(StateTransitionError):
        sm.set_state(AssistantState.PLANNING, "Direct jump invalid")

def test_tool_ranking_scorer():
    registry = ToolRegistry()
    tool = ApplicationLauncherTool()
    registry.register(tool)
    
    ranked = registry.find_and_rank_by_capability("open_application")
    assert len(ranked) == 1
    selected_tool, score = ranked[0]
    assert selected_tool.metadata.name == "app_launcher"
    assert score > 0.8

def test_prompt_manager_loading():
    pm = PromptManager()
    prompt = pm.get("planner", goal="Open Notepad", capabilities="open_application")
    assert "Open Notepad" in prompt
    assert "open_application" in prompt

@pytest.mark.asyncio
async def test_execution_plan_with_retries_and_tool_ranking():
    registry = ToolRegistry()
    tool = ApplicationLauncherTool()
    registry.register(tool)
    
    undo_mgr = UndoManager()
    state_mgr = StateManager()
    executor = PlanExecutor(registry, undo_mgr, state_mgr)
    cid = str(uuid.uuid4())
    
    plan = ExecutionPlanModel(
        correlation_id=cid,
        user_goal="Open Notepad",
        steps=[PlanStepModel(step_id=1, capability="open_application", args={"app_name": "notepad"}, expected_observation="App opened")]
    )
    
    results = await executor.execute_plan(plan)
    assert len(results) == 1
    assert results[0].status == "completed"
    assert results[0].correlation_id == cid
