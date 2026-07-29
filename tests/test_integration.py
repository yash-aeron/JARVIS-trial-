import pytest
import asyncio
import uuid
import os

from core.container import DependencyContainer
from core.app import JARVISApp, bootstrap_container
from core.interfaces import IEventBus, ISTTProvider, ITTSProvider, ILLMProvider
from core.models import (
    EventModel, ToolRequestModel, ToolResultModel, 
    SpeechRecognizedEventData, UserCommandResultModel, ServiceState
)
from core.event_bus import AsyncEventBus
from core.service_manager import ServiceManager
from state.state_manager import StateManager
from state.states import AssistantState
from tools.registry import ToolRegistry
from tools.system_tools import ApplicationLauncherTool
from tools.ranking_strategy import CompositeRankingStrategy
from brain.planner import Planner
from automation.executor import PlanExecutor
from memory.schema import MemoryItemModel
from memory.memory_manager import MemoryManager
from speech.speech_manager import SpeechManager

@pytest.mark.asyncio
async def test_e2e_conversational_speech_pipeline():
    """E2E Test: Speech Input -> STT -> Intent -> Decision -> Planner -> Executor -> Tool -> Speech Output."""
    container = bootstrap_container()
    app = JARVISApp(container)
    await app.initialize()
    
    speech_mgr: SpeechManager = container.resolve(SpeechManager)
    cid = str(uuid.uuid4())
    
    # 1. Process Speech Input Audio Stream
    text = await speech_mgr.process_speech_input(b"RIFF_AUDIO_DATA_SIMULATED", correlation_id=cid)
    assert isinstance(text, str)
    
    # 2. Execute User Command via App Orchestrator
    res: UserCommandResultModel = await app.process_user_command("Open notepad", correlation_id=cid)
    assert res.correlation_id == cid
    assert res.intent in ["SINGLE_TOOL", "MULTI_STEP_PLAN", "CONVERSATION"]

    # 3. Verify Persistent Event Sourcing Trail
    event_bus: AsyncEventBus = container.resolve(IEventBus)
    history = event_bus.get_event_history(correlation_id=cid)
    topics = [ev.topic for ev in history]

    assert "intent.detected" in topics

    await app.shutdown()

@pytest.mark.asyncio
async def test_e2e_event_sourcing_replay():
    """E2E Test: Verify SQLite event store records events and replays them cleanly."""
    db_path = "data/test_e2e_replay.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    event_bus = AsyncEventBus(db_path=db_path)
    cid = str(uuid.uuid4())
    
    ev1 = EventModel(correlation_id=cid, topic="speech.recognized", sender="STT", payload=SpeechRecognizedEventData(text="Open chrome"))
    ev2 = EventModel(correlation_id=cid, topic="tool.started", sender="Executor", payload=SpeechRecognizedEventData(text="App Launcher"))
    
    await event_bus.publish(ev1)
    await event_bus.publish(ev2)
    
    replayed_events = []
    async def capture_handler(ev: EventModel):
        replayed_events.append(ev)
        
    await event_bus.replay_events(correlation_id=cid, handler=capture_handler)
    assert len(replayed_events) == 2
    assert replayed_events[0].topic == "speech.recognized"
    assert replayed_events[1].topic == "tool.started"

@pytest.mark.asyncio
async def test_e2e_circuit_breaker_service_degradation():
    """E2E Test: ServiceManager tracks consecutive failures and degrades service state."""
    service_mgr = ServiceManager()
    
    class FailingService:
        @property
        def name(self) -> str:
            return "FailingSubsystem"
        async def start(self) -> None:
            raise RuntimeError("Subsystem boot failed")
        async def stop(self) -> None:
            pass
        async def health_check(self) -> bool:
            return False
            
    failing_svc = FailingService()
    service_mgr.register_service(failing_svc)
    
    # Trigger 3 consecutive start failures to trip circuit breaker
    await service_mgr.start_service("FailingSubsystem")
    await service_mgr.start_service("FailingSubsystem")
    await service_mgr.start_service("FailingSubsystem")
    
    state = service_mgr.get_service_state("FailingSubsystem")
    assert state == ServiceState.DEGRADED

@pytest.mark.asyncio
async def test_e2e_composite_tool_ranking_context_aware():
    """E2E Test: ToolRegistry ranks tools based on runtime window context and capability specialization."""
    ranking_strategy = CompositeRankingStrategy()
    registry = ToolRegistry(ranking_strategy=ranking_strategy)
    
    tool = ApplicationLauncherTool()
    registry.register(tool)
    
    from context.context_manager import ContextSnapshotModel
    context = ContextSnapshotModel(focused_app="VS Code", active_mode="Developer")
    ranked = registry.find_and_rank_by_capability("open_application", context=context)

    assert len(ranked) >= 1
    top_tool, score = ranked[0]
    assert top_tool.metadata.name == "app_launcher"
    assert score >= 0.80
