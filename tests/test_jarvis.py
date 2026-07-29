import pytest
import asyncio
import uuid

from core.interfaces import EventModel, ToolRequestModel
from core.event_bus import AsyncEventBus
from state.state_manager import StateManager
from state.states import AssistantState
from language.detector import CodeSwitchLanguageDetector
from tools.registry import ToolRegistry
from tools.system_tools import ApplicationLauncherTool
from brain.planner import Planner, ExecutionPlanModel, PlanStepModel
from brain.intent_engine import IntentEngine, IntentCategory
from agent.executive import ExecutiveAgent
from automation.executor import PlanExecutor
from automation.undo_manager import UndoManager
from memory.schema import MemoryItemModel
from memory.memory_manager import MemoryManager
from models.llm import OllamaLLMProvider

@pytest.mark.asyncio
async def test_event_bus_with_pydantic_and_correlation_id():
    bus = AsyncEventBus()
    received = []
    cid = str(uuid.uuid4())
    
    async def handler(ev: EventModel):
        received.append((ev.correlation_id, ev.data["msg"]))
        
    bus.subscribe("test.topic", handler)
    await bus.publish(EventModel(correlation_id=cid, topic="test.topic", data={"msg": "hello"}, sender="test"))
    
    assert len(received) == 1
    assert received[0][0] == cid
    assert received[0][1] == "hello"

def test_state_manager_with_correlation_id():
    sm = StateManager()
    cid = str(uuid.uuid4())
    assert sm.current_state == AssistantState.IDLE
    sm.set_state(AssistantState.PLANNING, "Testing state", correlation_id=cid)
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
    
    found = registry.find_by_capability("open_application")
    assert len(found) == 1
    assert found[0].metadata.name == "app_launcher"

@pytest.mark.asyncio
async def test_end_to_end_vertical_slice():
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
        steps=[PlanStepModel(step_id=1, capability="open_application", args={"app_name": "notepad"}, expected_observation="Notepad opened")]
    )
    
    results = await executor.execute_plan(plan)
    assert len(results) == 1
    assert results[0].status == "completed"
    assert results[0].correlation_id == cid

def test_memory_pydantic_persistence():
    mem_mgr = MemoryManager(db_path="data/test_memory.db")
    item = MemoryItemModel(content="User prefers dark mode", tags=["preference", "theme"], importance=4.5)
    item_id = mem_mgr.store(item)
    
    queried = mem_mgr.query(tag="preference")
    assert len(queried) >= 1
    assert queried[0].content == "User prefers dark mode"
