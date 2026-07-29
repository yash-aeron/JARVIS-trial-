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
    """Builds and wires the full dependency graph inside DependencyContainer using Factory Registration."""
    container = DependencyContainer()
    
    # 1. Register Core Singletons & Factories
    container.register_singleton(Settings, Settings())
    container.register_factory(IEventBus, lambda c: AsyncEventBus())
    
    # Enable shared event bus
    shared_bus = container.resolve(IEventBus)
    container.register_singleton(StateManager, StateManager(shared_bus))
    container.register_singleton(ServiceManager, ServiceManager())
    
    # 2. Register Language & Speech Services via Factories
    container.register_factory(LanguageManager, lambda c: LanguageManager(c.resolve(Settings)))
    container.register_factory(SpeechManager, lambda c: SpeechManager(
        stt=WhisperSTTProvider(),
        tts=EdgeTTSProvider(),
        language_manager=c.resolve(LanguageManager),
        state_manager=c.resolve(StateManager),
        event_bus=c.resolve(IEventBus)
    ))
    
    # Register SpeechManager as IService with ServiceManager
    service_mgr = container.resolve(ServiceManager)
    service_mgr.register_service(container.resolve(SpeechManager))
    
    # 3. Register Intelligence & Executive Agent Factories
    container.register_singleton(ILLMProvider, OllamaLLMProvider())
    container.register_factory(IntentEngine, lambda c: IntentEngine(c.resolve(ILLMProvider)))
    container.register_factory(ExecutiveAgent, lambda c: ExecutiveAgent(
        c.resolve(IntentEngine), 
        c.resolve(StateManager), 
        c.resolve(IEventBus)
    ))
    container.register_factory(Planner, lambda c: Planner(
        c.resolve(ILLMProvider), 
        c.resolve(StateManager), 
        c.resolve(IEventBus)
    ))
    
    # 4. Register Tools, Automation & Skills
    tool_reg = ToolRegistry()
    tool_reg.register(SystemControlTool())
    tool_reg.register(ApplicationLauncherTool())
    container.register_singleton(ToolRegistry, tool_reg)
    
    container.register_singleton(UndoManager, UndoManager())
    container.register_factory(PlanExecutor, lambda c: PlanExecutor(
        tool_registry=c.resolve(ToolRegistry),
        undo_manager=c.resolve(UndoManager),
        state_manager=c.resolve(StateManager),
        event_bus=c.resolve(IEventBus)
    ))
    container.register_factory(SkillEngine, lambda c: SkillEngine(c.resolve(ToolRegistry)))
    
    # 5. Register Auxiliary & Management Systems
    container.register_singleton(MemoryManager, MemoryManager())
    container.register_singleton(ContextManager, ContextManager())
    container.register_singleton(SessionManager, SessionManager())
    container.register_singleton(ModeManager, ModeManager(initial_mode="Developer"))
    container.register_factory(PluginManager, lambda c: PluginManager(c))
    
    return container

class JARVISApp:
    """Master Application Orchestrator resolved directly from DependencyContainer."""
    
    def __init__(self, container: Optional[DependencyContainer] = None):
        logger.info("Initializing JARVIS AI Operating System Assistant from DI Container Factory...")
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
            state_mgr.transition_to(AssistantState.IDLE, "Clarification requested", correlation_id=cid)
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
            state_mgr.transition_to(AssistantState.IDLE, "Response generated", correlation_id=cid)
            
        # Step 4: Speech Synthesis & Output
        await speech_mgr.speak(response, correlation_id=cid)
        
        return {
            "correlation_id": cid,
            "utterance": utterance,
            "intent": intent.category.value,
            "execution_results": results,
            "response": response
        }
