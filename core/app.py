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
from tools.system_tools import SystemControlTool, ApplicationLauncherTool, ContextReaderTool, MemoryManagementTool, WebSearchTool
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
    from agent.subagents import PlanningSubagent, MemorySubagent, ExecutionSubagent
    container.register_factory(PlanningSubagent, lambda c: PlanningSubagent(c.resolve(Planner), c.resolve(IEventBus)))
    container.register_factory(MemorySubagent, lambda c: MemorySubagent(c.resolve(MemoryManager), c.resolve(IEventBus)))
    container.register_factory(ExecutionSubagent, lambda c: ExecutionSubagent(c.resolve(PlanExecutor), c.resolve(IEventBus)))

    container.register_factory(ExecutiveAgent, lambda c: ExecutiveAgent(
        c.resolve(IntentEngine), 
        c.resolve(StateManager), 
        c.resolve(IEventBus),
        planning_subagent=c.resolve(PlanningSubagent),
        memory_subagent=c.resolve(MemorySubagent),
        execution_subagent=c.resolve(ExecutionSubagent)
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
    tool_reg.register(WebSearchTool())

    from vision.vision_service import ScreenshotCaptureTool
    tool_reg.register(ScreenshotCaptureTool())
    container.register_singleton(ToolRegistry, tool_reg)

    from security.permission_manager import PermissionManager
    container.register_singleton(PermissionManager, PermissionManager())

    container.register_singleton(UndoManager, UndoManager())
    container.register_factory(PlanExecutor, lambda c: PlanExecutor(
        tool_registry=c.resolve(ToolRegistry),
        undo_manager=c.resolve(UndoManager),
        state_manager=c.resolve(StateManager),
        event_bus=c.resolve(IEventBus),
        permission_manager=c.resolve(PermissionManager)
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
        self._chat_history: List[tuple] = []

    @property
    def state_manager(self) -> StateManager:
        return self.container.resolve(StateManager)

    @property
    def event_bus(self) -> IEventBus:
        return self.container.resolve(IEventBus)

    async def initialize(self) -> None:
        service_mgr: ServiceManager = self.container.resolve(ServiceManager)
        await service_mgr.start_all()
        
        # Discover and load installed third-party plugins
        plugin_mgr: PluginManager = self.container.resolve(PluginManager)
        loaded = await plugin_mgr.discover_and_load_all()
        if loaded:
            logger.info(f"[JARVISApp] Discovered and loaded third-party plugins: {loaded}")
            
        logger.info("JARVIS Subsystems online.")

    async def shutdown(self) -> None:
        service_mgr: ServiceManager = self.container.resolve(ServiceManager)
        await service_mgr.stop_all()
        logger.info("JARVIS Subsystems shutdown complete.")

    async def _converse(
        self,
        utterance: str,
        cid: str,
        context: Optional[ExecutionContextModel] = None,
    ) -> str:
        """Answer a conversational turn with the LLM, carrying short-term history."""
        state_mgr: StateManager = self.container.resolve(StateManager)
        state_mgr.transition_to(AssistantState.THINKING, "Composing reply", correlation_id=cid)

        llm: ILLMProvider = self.container.resolve(ILLMProvider)
        mode_mgr: ModeManager = self.container.resolve(ModeManager)

        focus = ""
        if context is not None and getattr(context, "focused_app", ""):
            focus = f"\nThe user is currently focused on: {context.focused_app}."

        history = ""
        if self._chat_history:
            turns = [f"User: {u}\nJARVIS: {a}" for u, a in self._chat_history[-6:]]
            history = "\n\nRecent conversation:\n" + "\n".join(turns)

        system_prompt = (
            "You are JARVIS, an AI assistant running locally on the user's Windows PC. "
            "You address the user as 'sir'. You are concise, dry, and quietly capable — "
            "never verbose or bubbly. Answer in one to three short sentences unless asked "
            "for detail. You can open applications, search the web, and report system "
            f"status when asked. Current mode: {mode_mgr.current_mode}.{focus}"
        )

        try:
            reply = await llm.generate(
                prompt=f"{history}\n\nUser: {utterance}\nJARVIS:".strip(),
                system_prompt=system_prompt,
                # Chat quality matters more than latency here; the smallest tier
                # drifts into third-person narration instead of answering.
                complexity_hint=TaskComplexity.MULTI_STEP_PLAN,
            )
            reply = (reply or "").strip()
        except Exception as exc:
            logger.error(f"[JARVISApp] Conversation generation failed: {exc}")
            reply = ""

        if not reply or reply.startswith("[JARVIS Fallback Engine]"):
            reply = "I'm online, sir, though my language model is unavailable at the moment."

        self._chat_history.append((utterance, reply))
        if len(self._chat_history) > 12:
            self._chat_history = self._chat_history[-12:]
        return reply

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
        
        # Snapshot desktop context up front: the executive needs it to enforce mode
        # constraints, and get_snapshot() blocks (Win32 + PowerShell), so keep it
        # off the event loop.
        runtime_context: ExecutionContextModel = await asyncio.to_thread(context_mgr.get_snapshot)

        # Step 1: Executive Agent Processing
        executive_res = await exec_agent.process(utterance, correlation_id=cid, context=runtime_context)

        intent: IntentResultModel = executive_res.intent
        decision: AgentDecisionModel = executive_res.decision
        
        results: List[ToolResultModel] = []
        if decision.needs_planning or intent.capabilities_needed:
            # Step 2: Capability Planning & Optimization
            plan: ExecutionPlanModel = await planner.create_plan(utterance, intent.capabilities_needed, correlation_id=cid)
            
            # Orchestrator publishes plan.created event
            plan_payload = PlanCreatedEventData(plan_id=plan.plan_id, correlation_id=cid, total_steps=len(plan.steps), user_goal=utterance)
            await event_bus.publish(EventModel(correlation_id=cid, topic="plan.created", payload=plan_payload, sender="JARVISApp"))
            
            # Step 3: Parallel Execution via Action Queue with ExecutionContextModel
            tool_results = await executor.execute_plan(plan, context=runtime_context)
            results = tool_results

            # Step 3b: Executive Reflection & Fallback Re-planning
            is_satisfied = exec_agent.reflect(utterance, results, expected_steps=len(plan.steps))
            if not is_satisfied:
                logger.warning(f"[JARVISApp] Reflection failed for '{utterance}'. Triggering fallback re-planning...")
                fallback_planner: FallbackPlanner = self.container.resolve(FallbackPlanner)
                fb_steps = fallback_planner.generate_fallback_steps(utterance)
                fb_plan = ExecutionPlanModel(correlation_id=cid, user_goal=utterance, steps=fb_steps)
                fb_results = await executor.execute_plan(fb_plan, context=runtime_context)
                # Keep the original failures alongside the fallback attempt so the
                # caller can see what actually happened.
                results = results + fb_results
                is_satisfied = exec_agent.reflect(utterance, fb_results)

            if is_satisfied:
                response = f"Sir, I have executed your request for '{utterance}'."
            else:
                failures = [r.error for r in results if getattr(r, "status", "") != "completed" and r.error]
                detail = f" ({failures[0]})" if failures else ""
                response = f"Sir, I was unable to complete your request for '{utterance}'.{detail}"
        else:
            # Conversational turn — answer with the LLM rather than a canned string.
            response = await self._converse(utterance, cid, runtime_context)
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
