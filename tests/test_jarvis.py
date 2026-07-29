import pytest
import asyncio

from core.event_bus import AsyncEventBus, Event
from state.state_manager import StateManager
from state.states import AssistantState
from language.detector import CodeSwitchLanguageDetector
from tools.registry import ToolRegistry
from tools.system_tools import ApplicationLauncherTool
from brain.planner import Planner, ExecutionPlan, PlanStep
from automation.executor import PlanExecutor
from automation.undo_manager import UndoManager
from memory.schema import MemoryItem
from memory.memory_manager import MemoryManager

@pytest.mark.asyncio
async def test_event_bus_and_store():
    bus = AsyncEventBus()
    received = []
    
    async def handler(ev: Event):
        received.append(ev.data["msg"])
        
    bus.subscribe("test.topic", handler)
    await bus.publish(Event(topic="test.topic", data={"msg": "hello"}, sender="test"))
    
    assert len(received) == 1
    assert received[0] == "hello"
    assert len(bus.get_event_history()) == 1

def test_state_manager():
    sm = StateManager()
    assert sm.current_state == AssistantState.IDLE
    sm.set_state(AssistantState.PLANNING, "Testing planning state")
    assert sm.current_state == AssistantState.PLANNING

def test_language_code_switching():
    detector = CodeSwitchLanguageDetector()
    res = detector.detect("Jarvis, Chrome kholo and search for Python tutorials")
    assert res["code_switching"] is True
    assert res["primary_language"] == "hi-IN"

def test_capability_discovery():
    registry = ToolRegistry()
    tool = ApplicationLauncherTool()
    registry.register(tool)
    
    found = registry.find_by_capability("app_automation")
    assert len(found) == 1
    assert found[0].metadata.name == "app_launcher"

@pytest.mark.asyncio
async def test_plan_execution_and_undo():
    registry = ToolRegistry()
    tool = ApplicationLauncherTool()
    registry.register(tool)
    
    undo_mgr = UndoManager()
    state_mgr = StateManager()
    executor = PlanExecutor(registry, undo_mgr, state_mgr)
    
    plan = ExecutionPlan(
        plan_id="p1",
        user_goal="Open VS Code",
        steps=[PlanStep(step_id=1, tool_name="app_launcher", args={"app_name": "VS Code", "action": "launch"}, expected_observation="App launched")]
    )
    
    results = await executor.execute_plan(plan)
    assert len(results) == 1
    assert results[0]["status"] == "completed"
    
    undo_res = await undo_mgr.rollback_last()
    assert undo_res["status"] == "undone"

def test_memory_tagged_persistence():
    mem_mgr = MemoryManager(db_path="data/test_memory.db")
    item = MemoryItem(content="User prefers dark mode", tags=["preference", "theme"], importance=4.5)
    item_id = mem_mgr.store(item)
    
    queried = mem_mgr.query(tag="preference")
    assert len(queried) >= 1
    assert queried[0].content == "User prefers dark mode"
