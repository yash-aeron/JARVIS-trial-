import pytest
import asyncio
import uuid

from core.container import DependencyContainer
from core.app import JARVISApp, bootstrap_container
from core.interfaces import IEventBus, ISTTProvider, ITTSProvider, ILLMProvider
from core.models import EventModel, ToolRequestModel, ToolResultModel, GenericEventData, SpeechRecognizedEventData, UserCommandResultModel
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
from prompts.prompt_manager import PromptManager

def test_strict_class_and_interface_di():
    container = bootstrap_container()
    app = JARVISApp(container)
    
    stt = container.resolve(ISTTProvider)
    tts = container.resolve(ITTSProvider)
    llm = container.resolve(ILLMProvider)
    prompt_mgr = container.resolve(PromptManager)
    
    assert stt is not None
    assert tts is not None
    assert llm is not None
    assert prompt_mgr is not None

def test_sqlite_event_sourcing_persistence():
    bus = AsyncEventBus(db_path="data/test_event_store.db")
    cid = str(uuid.uuid4())
    payload = SpeechRecognizedEventData(text="Testing event persistence")
    
    event = EventModel(correlation_id=cid, topic="speech.recognized", payload=payload, sender="test")
    asyncio.run(bus.publish(event))
    
    history = bus.get_event_history(correlation_id=cid)
    assert len(history) >= 1
    assert history[0].payload.text == "Testing event persistence"

def test_plan_validator_enhanced_checks():
    validator = PlanValidator()
    
    valid_json = {
        "steps": [
            {"step_id": 1, "capability": "open_application", "args": {"app_name": "notepad"}, "expected_observation": "Opened"}
        ]
    }
    plan = validator.validate_llm_json(valid_json, "Open Notepad", "cid_999")
    assert plan is not None
    assert len(plan.steps) == 1
    assert plan.steps[0].step_id == 1

def test_guarded_state_transition_to():
    sm = StateManager()
    sm.transition_to(AssistantState.LISTENING, "Listening")
    assert sm.current_state == AssistantState.LISTENING
    
    with pytest.raises(StateTransitionError):
        sm.transition_to(AssistantState.PLANNING, "Illegal transition")

def test_memory_retrieval_ranking_formula():
    mem_mgr = MemoryManager(db_path="data/test_ranked_mem.db")
    item1 = MemoryItemModel(content="User prefers dark theme", tags=["preference", "theme"], importance=4.5)
    item2 = MemoryItemModel(content="User bought milk", tags=["grocery"], importance=1.0)
    
    mem_mgr.store(item1)
    mem_mgr.store(item2)
    
    ranked = mem_mgr.query_and_rank(query_tags=["preference"])
    assert len(ranked) >= 1
    top_item, score = ranked[0]
    assert top_item.content == "User prefers dark theme"
    assert score > 3.0

@pytest.mark.asyncio
async def test_full_end_to_end_pipeline():
    app = JARVISApp()
    await app.initialize()
    
    res: UserCommandResultModel = await app.process_user_command("Open notepad")
    assert res.correlation_id is not None
    assert res.intent in ["SINGLE_TOOL", "MULTI_STEP_PLAN"]
    assert len(res.execution_results) >= 1
    assert res.execution_results[0].status == "completed"
    
    await app.shutdown()
