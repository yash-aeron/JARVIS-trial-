import uuid
import asyncio
from typing import Optional, Dict, Any, List

from config.settings import Settings
from core.container import DependencyContainer
from core.event_bus import AsyncEventBus
from core.service_manager import ServiceManager
from core.interfaces import IEventBus, IService, ILLMProvider, ISTTProvider, ITTSProvider, ITool, ISkill, IPlugin
from core.models import EventModel, ExecutionPlanModel, PlanCreatedEventData, UserCommandResultModel, ToolResultModel, ExecutionContextModel
from state.state_manager import StateManager
from state.states import AssistantState
from language.manager import LanguageManager
from prompts.prompt_manager import PromptManager

from models.llm import OllamaLLMProvider
from models.stt import WhisperSTTProvider
from models.tts import EdgeTTSProvider
from speech.speech_manager import SpeechManager

from brain.intent_engine import IntentEngine, IntentResultModel
from brain.planner import Planner
from brain.plan_validator import PlanValidator
from brain.fallback_planner import FallbackPlanner
from brain.plan_optimizer import PlanOptimizer
from agent.executive import ExecutiveAgent, AgentDecisionModel

from tools.registry import ToolRegistry
from tools.system_tools import SystemControlTool, ApplicationLauncherTool, ContextReaderTool, MemoryManagementTool
from automation.undo_manager import UndoManager
from automation.executor import PlanExecutor
from skills.skill_engine import SkillEngine

from memory.memory_manager import MemoryManager
from context.context_manager import ContextManager
from session.session_manager import SessionManager
from system.mode_manager import ModeManager
from plugins.plugin_manager import PluginManager
from observability.logger import logger

def _register_foundation(container: DependencyContainer) -> None:
    settings = Settings()
    event_bus = AsyncEventBus()
    state_manager = StateManager(event_bus)
    service_manager = ServiceManager()
    prompt_manager = PromptManager()
    
    container.register_singleton(Settings, settings)
    container.register_singleton(IEventBus, event_bus)
    container.register_singleton(StateManager, state_manager)
    container.register_singleton(ServiceManager, service_manager)
    container.register_singleton(PromptManager, prompt_manager)

def _register_speech(container: DependencyContainer) -> None:
    settings = container.resolve(Settings)
    stt_choice = settings.get("models.stt_provider", "whisper")
    tts_choice = settings.get("models.tts_provider", "edge-tts")
    
    stt_provider = WhisperSTTProvider() if stt_choice == "whisper" else WhisperSTTProvider()
    tts_provider = EdgeTTSProvider() if tts_choice == "edge-tts" else EdgeTTSProvider()
    
    container.register_singleton(ISTTProvider, stt_provider)
    container.register_singleton(ITTSProvider, tts_provider)
    
    container.register_factory(LanguageManager, lambda c: LanguageManager(c.resolve(Settings)))
    container.register_factory(SpeechManager, lambda c: SpeechManager(
        stt=c.resolve(ISTTProvider),
        tts=c.resolve(ITTSProvider),
        language_manager=c.resolve(LanguageManager),
        state_manager=c.resolve(StateManager),
        event_bus=c.resolve(IEventBus)
    ))
    
    service_mgr = container.resolve(ServiceManager)
    service_mgr.register_service(container.resolve(SpeechManager))

def _register_brain(container: DependencyContainer) -> None:
    settings = container.resolve(Settings)
    llm_choice = settings.get("models.llm_provider", "ollama")
    llm_provider = OllamaLLMProvider() if llm_choice == "ollama" else OllamaLLMProvider()
    
    container.register_singleton(ILLMProvider, llm_provider)
    container.register_singleton(PlanValidator, PlanValidator())
    container.register_singleton(FallbackPlanner, FallbackPlanner())
    container.register_singleton(PlanOptimizer, PlanOptimizer())
    
    container.register_factory(IntentEngine, lambda c: IntentEngine(c.resolve(ILLMProvider)))
    container.register_factory(ExecutiveAgent, lambda c: ExecutiveAgent(
        c.resolve(IntentEngine), 
        c.resolve(StateManager), 
        c.resolve(IEventBus)
    ))
    container.register_factory(Planner, lambda c: Planner(
        llm=c.resolve(ILLMProvider), 
        state_manager=c.resolve(StateManager), 
        prompt_manager=c.resolve(PromptManager),
        validator=c.resolve(PlanValidator),
        fallback_planner=c.resolve(FallbackPlanner),
        optimizer=c.resolve(PlanOptimizer),
        event_bus=c.resolve(IEventBus)
    ))

def _register_memory(container: DependencyContainer) -> None:
    container.register_singleton(MemoryManager, MemoryManager())
    container.register_singleton(ContextManager, ContextManager())
    container.register_singleton(SessionManager, SessionManager())
    container.register_singleton(ModeManager, ModeManager(initial_mode="Developer"))

def _register_automation(container: DependencyContainer) -> None:
    context_mgr = container.resolve(ContextManager)
    memory_mgr = container.resolve(MemoryManager)
    tool_reg = ToolRegistry()
    tool_reg.register(SystemControlTool())
    tool_reg.register(ApplicationLauncherTool())
    tool_reg.register(ContextReaderTool(context_manager=context_mgr))
    tool_reg.register(MemoryManagementTool(memory_manager=memory_mgr))
    container.register_singleton(ToolRegistry, tool_reg)

    container.register_singleton(UndoManager, UndoManager())
    container.register_factory(PlanExecutor, lambda c: PlanExecutor(
        tool_registry=c.resolve(ToolRegistry),
        undo_manager=c.resolve(UndoManager),
        state_manager=c.resolve(StateManager),
        event_bus=c.resolve(IEventBus)
    ))
    container.register_factory(SkillEngine, lambda c: SkillEngine(c.resolve(ToolRegistry)))

def _register_plugins(container: DependencyContainer) -> None:
    container.register_factory(PluginManager, lambda c: PluginManager(c))

def bootstrap_container() -> DependencyContainer:
    """Builds and wires the full dependency graph inside DependencyContainer via Modular Registration functions."""
    container = DependencyContainer()

    _register_foundation(container)
    _register_speech(container)
    _register_brain(container)
    _register_memory(container)        # must precede automation (ContextReaderTool needs ContextManager)
    _register_automation(container)
    _register_plugins(container)

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

    async def process_user_command(self, utterance: str, correlation_id: Optional[str] = None) -> UserCommandResultModel:
        cid = correlation_id or str(uuid.uuid4())
        logger.info(f"[USER COMMAND] [CID: {cid}]: '{utterance}'")
        
        exec_agent: ExecutiveAgent = self.container.resolve(ExecutiveAgent)
        planner: Planner = self.container.resolve(Planner)
        executor: PlanExecutor = self.container.resolve(PlanExecutor)
        speech_mgr: SpeechManager = self.container.resolve(SpeechManager)
        state_mgr: StateManager = self.container.resolve(StateManager)
        context_mgr: ContextManager = self.container.resolve(ContextManager)
        event_bus: IEventBus = self.container.resolve(IEventBus)
        
        # Step 1: Executive Agent Processing
        executive_res = await exec_agent.process(utterance, correlation_id=cid)
        intent: IntentResultModel = executive_res["intent"]
        decision: AgentDecisionModel = executive_res["decision"]
        
        results: List[ToolResultModel] = []
        if decision.needs_clarification:
            response = decision.clarification_prompt or "Could you please clarify your request?"
            state_mgr.transition_to(AssistantState.IDLE, "Clarification requested", correlation_id=cid)
        elif decision.needs_planning or intent.capabilities_needed:
            # Step 2: Capability Planning & Optimization
            plan: ExecutionPlanModel = await planner.create_plan(utterance, intent.capabilities_needed, correlation_id=cid)
            
            # Orchestrator publishes plan.created event
            plan_payload = PlanCreatedEventData(plan_id=plan.plan_id, correlation_id=cid, total_steps=len(plan.steps), user_goal=utterance)
            await event_bus.publish(EventModel(correlation_id=cid, topic="plan.created", payload=plan_payload, sender="JARVISApp"))
            
            # Step 3: Parallel Execution via Action Queue with ExecutionContextModel
            runtime_context: ExecutionContextModel = context_mgr.get_snapshot()
            tool_results = await executor.execute_plan(plan, context=runtime_context)
            results = tool_results
            response = f"Sir, I have executed your request for '{utterance}'."
        else:
            response = f"Sir, I am online and listening: '{utterance}'."
            state_mgr.transition_to(AssistantState.IDLE, "Response generated", correlation_id=cid)
            
        # Step 4: Speech Synthesis & Output
        await speech_mgr.speak(response, correlation_id=cid)
        
        return UserCommandResultModel(
            correlation_id=cid,
            utterance=utterance,
            intent=intent.category.value,
            execution_results=results,
            response=response
        )
