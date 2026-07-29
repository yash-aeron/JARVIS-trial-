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

class JARVISApp:
    """Master Application Orchestrator built on Type-Based Dependency Injection."""
    
    def __init__(self):
        logger.info("Initializing JARVIS AI Operating System Assistant via Type-Based Dependency Injection...")
        
        self.container = DependencyContainer()
        
        # 1. Register Core Singletons using Interface/Type Keys
        self.settings = Settings()
        self.event_bus = AsyncEventBus()
        self.state_manager = StateManager(self.event_bus)
        self.service_manager = ServiceManager()
        
        self.container.register_singleton(Settings, self.settings)
        self.container.register_singleton(IEventBus, self.event_bus)
        self.container.register_singleton(StateManager, self.state_manager)
        self.container.register_singleton(ServiceManager, self.service_manager)
        
        # 2. Register Speech & Language Services
        self.language_manager = LanguageManager(self.settings)
        self.stt_provider = WhisperSTTProvider()
        self.tts_provider = EdgeTTSProvider()
        self.speech_manager = SpeechManager(
            stt=self.stt_provider,
            tts=self.tts_provider,
            language_manager=self.language_manager,
            state_manager=self.state_manager,
            event_bus=self.event_bus
        )
        
        self.container.register_singleton(LanguageManager, self.language_manager)
        self.container.register_singleton(SpeechManager, self.speech_manager)
        self.service_manager.register_service(self.speech_manager)
        
        # 3. Register Brain & Intelligence Services
        self.llm_provider = OllamaLLMProvider()
        self.intent_engine = IntentEngine(self.llm_provider)
        self.executive_agent = ExecutiveAgent(self.intent_engine, self.state_manager, self.event_bus)
        self.planner = Planner(self.llm_provider, self.state_manager, self.event_bus)
        
        self.container.register_singleton(ILLMProvider, self.llm_provider)
        self.container.register_singleton(IntentEngine, self.intent_engine)
        self.container.register_singleton(ExecutiveAgent, self.executive_agent)
        self.container.register_singleton(Planner, self.planner)
        
        # 4. Register Tool & Automation Systems
        self.tool_registry = ToolRegistry()
        self.tool_registry.register(SystemControlTool())
        self.tool_registry.register(ApplicationLauncherTool())
        
        self.undo_manager = UndoManager()
        self.executor = PlanExecutor(
            tool_registry=self.tool_registry,
            undo_manager=self.undo_manager,
            state_manager=self.state_manager,
            event_bus=self.event_bus
        )
        self.skill_engine = SkillEngine(self.tool_registry)
        
        self.container.register_singleton(ToolRegistry, self.tool_registry)
        self.container.register_singleton(UndoManager, self.undo_manager)
        self.container.register_singleton(PlanExecutor, self.executor)
        self.container.register_singleton(SkillEngine, self.skill_engine)
        
        # 5. Register Memory, Context & Auxiliary Systems
        self.memory_manager = MemoryManager()
        self.context_manager = ContextManager()
        self.session_manager = SessionManager()
        self.mode_manager = ModeManager(initial_mode="Developer")
        self.plugin_manager = PluginManager(self.container)
        
        self.container.register_singleton(MemoryManager, self.memory_manager)
        self.container.register_singleton(ContextManager, self.context_manager)
        self.container.register_singleton(SessionManager, self.session_manager)
        self.container.register_singleton(ModeManager, self.mode_manager)
        self.container.register_singleton(PluginManager, self.plugin_manager)

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
        
        # Resolve dependencies via type/interface keys
        exec_agent: ExecutiveAgent = self.container.resolve(ExecutiveAgent)
        planner: Planner = self.container.resolve(Planner)
        executor: PlanExecutor = self.container.resolve(PlanExecutor)
        speech_mgr: SpeechManager = self.container.resolve(SpeechManager)
        
        # Step 1: Executive Agent Processing
        executive_res = await exec_agent.process(utterance, correlation_id=cid)
        intent: IntentResultModel = executive_res["intent"]
        decision: AgentDecisionModel = executive_res["decision"]
        
        results = []
        if decision.needs_clarification:
            response = decision.clarification_prompt or "Could you please clarify your request?"
            self.state_manager.set_state(AssistantState.IDLE, "Clarification requested", correlation_id=cid)
        elif decision.needs_planning or intent.capabilities_needed:
            # Step 2: Capability Planning
            plan: ExecutionPlanModel = await planner.create_plan(utterance, intent.capabilities_needed, correlation_id=cid)
            
            # Step 3: Execution via Action Queue with Retries & Tool Ranking
            tool_results = await executor.execute_plan(plan)
            results = [tr.model_dump() for tr in tool_results]
            response = f"Sir, I have executed your request for '{utterance}'."
        else:
            response = f"Sir, I am online and listening: '{utterance}'."
            self.state_manager.set_state(AssistantState.IDLE, "Response generated", correlation_id=cid)
            
        # Step 4: Speech Synthesis & Output
        await speech_mgr.speak(response, correlation_id=cid)
        
        return {
            "correlation_id": cid,
            "utterance": utterance,
            "intent": intent.category.value,
            "execution_results": results,
            "response": response
        }
