import uuid
import asyncio
from typing import Optional, Dict, Any, List

from config.settings import Settings
from core.container import DependencyContainer
from core.event_bus import AsyncEventBus
from core.service_manager import ServiceManager
from core.interfaces import IEventBus, IService, ILLMProvider, ISTTProvider, ITTSProvider, ITool, ISkill, IPlugin
from core.models import EventModel
from state.state_manager import StateManager
from state.states import AssistantState
from language.manager import LanguageManager

from models.llm import OllamaLLMProvider
from models.stt import WhisperSTTProvider
from models.tts import EdgeTTSProvider
from speech.speech_manager import SpeechManager

from brain.intent_engine import IntentEngine, IntentResultModel
from brain.planner import Planner, ExecutionPlanModel
from agent.executive import ExecutiveAgent, AgentDecisionModel

from tools.registry import ToolRegistry
from tools.system_tools import SystemControlTool, ApplicationLauncherTool
from automation.undo_manager import UndoManager
from automation.executor import PlanExecutor
from skills.skill_engine import SkillEngine

from memory.memory_manager import MemoryManager
from context.context_manager import ContextManager
from session.session_manager import SessionManager
from system.mode_manager import ModeManager
from plugins.plugin_manager import PluginManager
from observability.logger import logger

def bootstrap_container() -> DependencyContainer:
    """Builds and wires the full dependency graph inside DependencyContainer."""
    container = DependencyContainer()
    
    # Core Infrastructure Factories & Singletons
    settings = Settings()
    event_bus = AsyncEventBus()
    state_manager = StateManager(event_bus)
    service_manager = ServiceManager()
    
    container.register_singleton(Settings, settings)
    container.register_singleton(IEventBus, event_bus)
    container.register_singleton(StateManager, state_manager)
    container.register_singleton(ServiceManager, service_manager)
    
    # Language & Speech
    language_manager = LanguageManager(settings)
    stt_provider = WhisperSTTProvider()
    tts_provider = EdgeTTSProvider()
    speech_manager = SpeechManager(
        stt=stt_provider,
        tts=tts_provider,
        language_manager=language_manager,
        state_manager=state_manager,
        event_bus=event_bus
    )
    container.register_singleton(LanguageManager, language_manager)
    container.register_singleton(SpeechManager, speech_manager)
    service_manager.register_service(speech_manager)
    
    # Intelligence & Executive Agent
    llm_provider = OllamaLLMProvider()
    intent_engine = IntentEngine(llm_provider)
    executive_agent = ExecutiveAgent(intent_engine, state_manager, event_bus)
    planner = Planner(llm_provider, state_manager, event_bus)
    
    container.register_singleton(ILLMProvider, llm_provider)
    container.register_singleton(IntentEngine, intent_engine)
    container.register_singleton(ExecutiveAgent, executive_agent)
    container.register_singleton(Planner, planner)
    
    # Tools, Skills & Automation
    tool_registry = ToolRegistry()
    tool_registry.register(SystemControlTool())
    tool_registry.register(ApplicationLauncherTool())
    
    undo_manager = UndoManager()
    executor = PlanExecutor(
        tool_registry=tool_registry,
        undo_manager=undo_manager,
        state_manager=state_manager,
        event_bus=event_bus
    )
    skill_engine = SkillEngine(tool_registry)
    
    container.register_singleton(ToolRegistry, tool_registry)
    container.register_singleton(UndoManager, undo_manager)
    container.register_singleton(PlanExecutor, executor)
    container.register_singleton(SkillEngine, skill_engine)
    
    # Auxiliary & Management Systems
    memory_manager = MemoryManager()
    context_manager = ContextManager()
    session_manager = SessionManager()
    mode_manager = ModeManager(initial_mode="Developer")
    plugin_manager = PluginManager(container)
    
    container.register_singleton(MemoryManager, memory_manager)
    container.register_singleton(ContextManager, context_manager)
    container.register_singleton(SessionManager, session_manager)
    container.register_singleton(ModeManager, mode_manager)
    container.register_singleton(PluginManager, plugin_manager)
    
    return container

class JARVISApp:
    """Master Application Orchestrator resolved directly from DependencyContainer."""
    
    def __init__(self, container: Optional[DependencyContainer] = None):
        logger.info("Initializing JARVIS AI Operating System Assistant from DI Container...")
        self.container = container or bootstrap_container()
        self.container.register_singleton(JARVISApp, self)

    async def initialize(self) -> None:
        service_mgr: ServiceManager = self.container.resolve(ServiceManager)
        await service_mgr.start_all()
        logger.info("JARVIS Subsystems online.")

    async def shutdown(self) -> None:
        service_mgr: ServiceManager = self.container.resolve(ServiceManager)
        await service_mgr.stop_all()
        logger.info("JARVIS Subsystems shutdown complete.")

    async def process_user_command(self, utterance: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        cid = correlation_id or str(uuid.uuid4())
        logger.info(f"[USER COMMAND] [CID: {cid}]: '{utterance}'")
        
        exec_agent: ExecutiveAgent = self.container.resolve(ExecutiveAgent)
        planner: Planner = self.container.resolve(Planner)
        executor: PlanExecutor = self.container.resolve(PlanExecutor)
        speech_mgr: SpeechManager = self.container.resolve(SpeechManager)
        state_mgr: StateManager = self.container.resolve(StateManager)
        context_mgr: ContextManager = self.container.resolve(ContextManager)
        
        # Step 1: Executive Agent Processing
        executive_res = await exec_agent.process(utterance, correlation_id=cid)
        intent: IntentResultModel = executive_res["intent"]
        decision: AgentDecisionModel = executive_res["decision"]
        
        results = []
        if decision.needs_clarification:
            response = decision.clarification_prompt or "Could you please clarify your request?"
            state_mgr.set_state(AssistantState.IDLE, "Clarification requested", correlation_id=cid)
        elif decision.needs_planning or intent.capabilities_needed:
            # Step 2: Capability Planning
            plan: ExecutionPlanModel = await planner.create_plan(utterance, intent.capabilities_needed, correlation_id=cid)
            
            # Step 3: Parallel Execution via Action Queue with Runtime Context & Retries
            runtime_context = context_mgr.get_snapshot().model_dump()
            tool_results = await executor.execute_plan(plan, context=runtime_context)
            results = [tr.model_dump() for tr in tool_results]
            response = f"Sir, I have executed your request for '{utterance}'."
        else:
            response = f"Sir, I am online and listening: '{utterance}'."
            state_mgr.set_state(AssistantState.IDLE, "Response generated", correlation_id=cid)
            
        # Step 4: Speech Synthesis & Output
        await speech_mgr.speak(response, correlation_id=cid)
        
        return {
            "correlation_id": cid,
            "utterance": utterance,
            "intent": intent.category.value,
            "execution_results": results,
            "response": response
        }
