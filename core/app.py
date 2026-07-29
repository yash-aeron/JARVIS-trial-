import asyncio
from typing import Optional, Dict, Any

from config.settings import Settings
from core.container import DependencyContainer
from core.event_bus import AsyncEventBus, Event
from core.service_manager import ServiceManager
from state.state_manager import StateManager
from state.states import AssistantState
from language.manager import LanguageManager

from models.llm import OllamaLLMProvider
from models.stt import WhisperSTTProvider
from models.tts import EdgeTTSProvider
from speech.speech_manager import SpeechManager

from brain.intent_engine import IntentEngine
from brain.planner import Planner
from agent.executive import ExecutiveAgent

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
    """Master Application Orchestrator initializing and coordinating all JARVIS subsystems."""
    
    def __init__(self):
        logger.info("Initializing JARVIS AI Operating System Assistant Master Core...")
        
        # 1. Foundation & Configuration
        self.settings = Settings()
        self.container = DependencyContainer()
        self.event_bus = AsyncEventBus()
        self.state_manager = StateManager(self.event_bus)
        self.service_manager = ServiceManager()
        
        # Register Core Singletons
        self.container.register_singleton("Settings", self.settings)
        self.container.register_singleton("AsyncEventBus", self.event_bus)
        self.container.register_singleton("StateManager", self.state_manager)
        
        # 2. Language & Speech
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
        self.service_manager.register_service(self.speech_manager)
        
        # 3. LLM & Brain & Executive Agent
        self.llm_provider = OllamaLLMProvider()
        self.intent_engine = IntentEngine(self.llm_provider)
        self.executive_agent = ExecutiveAgent(self.intent_engine, self.state_manager)
        self.planner = Planner(self.llm_provider, self.state_manager)
        
        # 4. Tools, Automation & Skills
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
        
        # 5. Memory, Context, Sessions & Modes
        self.memory_manager = MemoryManager()
        self.context_manager = ContextManager()
        self.session_manager = SessionManager()
        self.mode_manager = ModeManager(initial_mode="Developer")
        self.plugin_manager = PluginManager(self.container)

    async def initialize(self) -> None:
        await self.service_manager.start_all()
        logger.info("JARVIS Subsystems initialized successfully.")

    async def shutdown(self) -> None:
        await self.service_manager.stop_all()
        logger.info("JARVIS Shutdown complete.")

    async def process_user_command(self, utterance: str) -> Dict[str, Any]:
        """Core execution pipeline: Utterance -> Executive Agent -> Intent -> Planner -> Executor -> Response."""
        logger.info(f"[USER COMMAND]: {utterance}")
        
        # Executive Agent Evaluation
        executive_res = await self.executive_agent.process(utterance)
        intent = executive_res["intent"]
        decision = executive_res["decision"]
        
        results = []
        if decision.needs_planning:
            # Multi-step Plan Execution
            plan = await self.planner.create_plan(utterance, intent.capabilities_needed)
            results = await self.executor.execute_plan(plan)
            response = f"Sir, I have executed your plan for '{utterance}' across {len(plan.steps)} steps."
        else:
            # Single action or natural dialogue
            if intent.capabilities_needed:
                tool = self.tool_registry.get("app_launcher")
                if tool:
                    res = await tool.execute(app_name="VS Code", action="launch")
                    results.append(res)
            response = f"Sir, I have processed your command: '{utterance}'."
            self.state_manager.set_state(AssistantState.IDLE, "Command response generated")
            
        await self.speech_manager.speak(response)
        
        return {
            "utterance": utterance,
            "intent": intent.category.name,
            "execution_results": results,
            "response": response
        }
