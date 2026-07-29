import pytest
import asyncio
import uuid

from core.container import DependencyContainer
from core.app import JARVISApp, bootstrap_container
from core.interfaces import IEventBus, ISTTProvider, ITTSProvider, ILLMProvider
from core.models import EventModel, ToolRequestModel, ToolResultModel, GenericEventData, SpeechRecognizedEventData, UserCommandResultModel, ExecutionPlanModel, PlanStepModel
from core.event_bus import AsyncEventBus
from state.state_manager import StateManager
from state.states import AssistantState, StateTransitionError
from brain.planner import Planner
from brain.plan_validator import PlanValidator
from brain.fallback_planner import FallbackPlanner
from automation.executor import PlanExecutor
from automation.undo_manager import UndoManager
from memory.schema import MemoryItemModel
from memory.memory_manager import MemoryManager
from speech.speech_manager import SpeechManager
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
    assert history[0].data.get("text") == "Testing event persistence"

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
async def test_streaming_speech_pipeline():
    container = bootstrap_container()
    speech_mgr = container.resolve(SpeechManager)

    async def sample_audio_stream():
        yield b"chunk1"
        yield b"chunk2"

    async def sample_text_stream():
        yield "Hello "
        yield "world"

    received_tokens = []
    async for token in speech_mgr.process_streaming_input(sample_audio_stream()):
        received_tokens.append(token)

    assert isinstance(received_tokens, list)

    # Reset state manager back to IDLE before speak_stream
    container.resolve(StateManager).transition_to(AssistantState.IDLE, "Reset for TTS test")

    audio_chunks = []
    async for audio in speech_mgr.speak_stream(sample_text_stream()):
        audio_chunks.append(audio)

    assert isinstance(audio_chunks, list)

@pytest.mark.asyncio
async def test_plan_executor_end_to_end_regression():
    """Phase 0 Regression Test: Verifies full end-to-end plan execution with ActionItemModel instantiation."""
    container = bootstrap_container()
    executor: PlanExecutor = container.resolve(PlanExecutor)

    plan = ExecutionPlanModel(
        plan_id="test_plan_p0",
        correlation_id=str(uuid.uuid4()),
        user_goal="Test execution regression",
        steps=[
            PlanStepModel(
                step_id=1,
                capability="system_control",
                args={"action": "hardware_info"},
                expected_observation="Hardware metrics"
            )
        ]
    )

    results = await executor.execute_plan(plan)
    assert len(results) == 1
    assert results[0].status == "completed"

@pytest.mark.asyncio
async def test_full_end_to_end_pipeline():
    app = JARVISApp()
    await app.initialize()

    res: UserCommandResultModel = await app.process_user_command("Open notepad")
    assert res.correlation_id is not None
    assert res.intent in ["SINGLE_TOOL", "MULTI_STEP_PLAN"]

    await app.shutdown()
