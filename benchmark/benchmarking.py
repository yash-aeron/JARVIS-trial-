import time
import asyncio
import uuid
from core.container import DependencyContainer
from core.app import bootstrap_container
from core.interfaces import IEventBus
from core.models import BenchmarkResultModel, EventModel, SpeechRecognizedEventData, ExecutionPlanModel, PlanStepModel
from memory.memory_manager import MemoryManager
from memory.schema import MemoryItemModel
from tools.system_tools import ApplicationLauncherTool
from core.models.tools import ToolRequestModel
from brain.planner import Planner
from automation.executor import PlanExecutor
from observability.logger import logger

class SystemBenchmarking:
    """Automated benchmark runner evaluating system startup time, planner, executor, event bus, memory retrieval, and tool execution latencies."""
    
    async def run_all_benchmarks(self) -> BenchmarkResultModel:
        logger.info("Starting JARVIS Automated Benchmarking Suite...")
        
        # 1. Measure System Startup Time
        t0 = time.perf_counter()
        container = bootstrap_container()
        startup_lat = (time.perf_counter() - t0) * 1000.0
        
        # 2. Measure Event Bus Latency
        event_bus = container.resolve(IEventBus)
        cid = str(uuid.uuid4())
        ev = EventModel(correlation_id=cid, topic="speech.recognized", sender="benchmark", payload=SpeechRecognizedEventData(text="Benchmarking"))
        t0 = time.perf_counter()
        await event_bus.publish(ev)
        event_bus_lat = (time.perf_counter() - t0) * 1000.0
        
        # 3. Measure Memory Retrieval Latency
        mem_mgr: MemoryManager = container.resolve(MemoryManager)
        mem_mgr.store(MemoryItemModel(content="Benchmark test memory item for latency timing", tags=["benchmark"]))
        t0 = time.perf_counter()
        mem_mgr.semantic_recall("latency timing", top_k=1)
        memory_lat = (time.perf_counter() - t0) * 1000.0
        
        # 4. Measure Tool Execution Latency
        tool = ApplicationLauncherTool()
        req = ToolRequestModel(correlation_id=cid, capability="open_application", tool_name="app_launcher", args={"app_name": "notepad", "action": "focus"})
        t0 = time.perf_counter()
        await tool.execute(req)
        tool_lat = (time.perf_counter() - t0) * 1000.0
        
        # 5. Measure Planner Latency
        planner: Planner = container.resolve(Planner)
        t0 = time.perf_counter()
        plan = await planner.create_plan("Open notepad and check status", ["open_application"], cid)
        planner_lat = (time.perf_counter() - t0) * 1000.0
        
        # 6. Measure Executor Latency
        executor: PlanExecutor = container.resolve(PlanExecutor)
        t0 = time.perf_counter()
        await executor.execute_plan(plan)
        executor_lat = (time.perf_counter() - t0) * 1000.0
        
        res = BenchmarkResultModel(
            startup_time_ms=round(startup_lat, 3),
            planner_latency_ms=round(planner_lat, 3),
            executor_latency_ms=round(executor_lat, 3),
            event_bus_latency_ms=round(event_bus_lat, 3),
            memory_retrieval_latency_ms=round(memory_lat, 3),
            tool_execution_latency_ms=round(tool_lat, 3)
        )
        logger.info(f"Benchmarking completed: {res.model_dump()}")
        return res
