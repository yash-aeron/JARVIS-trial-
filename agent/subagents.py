"""
agent/subagents.py — Dedicated Subagents communicating over AsyncEventBus.

Specialized subagents:
  1. PlanningSubagent   — Responsible for task decomposition and execution plan generation.
  2. MemorySubagent     — Responsible for semantic recall, procedural matching, and episodic storage.
  3. ExecutionSubagent  — Responsible for executing action steps via PlanExecutor and tools.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from core.interfaces import IEventBus
from core.models import EventModel, ExecutionPlanModel, ExecutionContextModel
from brain.planner import Planner
from memory.memory_manager import MemoryManager
from automation.executor import PlanExecutor
from observability.logger import logger


class SubagentTaskRequestModel(BaseModel):
    task_id: str
    correlation_id: str
    target_subagent: str  # planning | memory | execution
    prompt: str
    context: Optional[Dict[str, Any]] = None


class SubagentTaskResultModel(BaseModel):
    task_id: str
    correlation_id: str
    subagent: str
    status: str  # completed | failed
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class BaseSubagent:
    """Base class for event-driven dedicated subagents."""

    def __init__(self, name: str, event_bus: Optional[IEventBus] = None):
        self.name = name
        self.event_bus = event_bus

    async def publish_result(self, result: SubagentTaskResultModel) -> None:
        if self.event_bus:
            event = EventModel(
                correlation_id=result.correlation_id,
                topic=f"subagent.{self.name}.completed",
                payload=result.model_dump(),
                sender=self.name
            )
            await self.event_bus.publish(event)


class PlanningSubagent(BaseSubagent):
    """Subagent handling task decomposition and multi-step plan generation."""

    def __init__(self, planner: Planner, event_bus: Optional[IEventBus] = None):
        super().__init__(name="planning", event_bus=event_bus)
        self.planner = planner

    async def handle_planning_task(self, req: SubagentTaskRequestModel) -> SubagentTaskResultModel:
        logger.info(f"[PlanningSubagent] Processing planning task for prompt: '{req.prompt}'")
        try:
            plan: ExecutionPlanModel = await self.planner.create_plan(
                goal=req.prompt,
                capabilities_needed=(req.context or {}).get("capabilities", []),
                correlation_id=req.correlation_id
            )
            res = SubagentTaskResultModel(
                task_id=req.task_id,
                correlation_id=req.correlation_id,
                subagent=self.name,
                status="completed",
                output=plan.model_dump()
            )
        except Exception as e:
            logger.error(f"[PlanningSubagent] Error creating plan: {e}")
            res = SubagentTaskResultModel(
                task_id=req.task_id,
                correlation_id=req.correlation_id,
                subagent=self.name,
                status="failed",
                error=str(e)
            )

        await self.publish_result(res)
        return res


class MemorySubagent(BaseSubagent):
    """Subagent handling semantic memory recall and procedural sequence matching."""

    def __init__(self, memory_manager: MemoryManager, event_bus: Optional[IEventBus] = None):
        super().__init__(name="memory", event_bus=event_bus)
        self.memory_manager = memory_manager

    async def handle_memory_task(self, req: SubagentTaskRequestModel) -> SubagentTaskResultModel:
        logger.info(f"[MemorySubagent] Recalling memories for query: '{req.prompt}'")
        try:
            semantic_memories = self.memory_manager.semantic_recall(query_text=req.prompt, top_k=3)
            procedural = self.memory_manager.recall_procedural(user_goal=req.prompt)

            serialized_semantic = [
                {"content": item.content, "score": score, "tags": item.tags}
                for item, score in semantic_memories
            ]
            output = {
                "semantic": serialized_semantic,
                "procedural": procedural.model_dump() if procedural else None
            }

            res = SubagentTaskResultModel(
                task_id=req.task_id,
                correlation_id=req.correlation_id,
                subagent=self.name,
                status="completed",
                output=output
            )
        except Exception as e:
            logger.error(f"[MemorySubagent] Error querying memory: {e}")
            res = SubagentTaskResultModel(
                task_id=req.task_id,
                correlation_id=req.correlation_id,
                subagent=self.name,
                status="failed",
                error=str(e)
            )

        await self.publish_result(res)
        return res


class ExecutionSubagent(BaseSubagent):
    """Subagent handling step execution via PlanExecutor."""

    def __init__(self, plan_executor: PlanExecutor, event_bus: Optional[IEventBus] = None):
        super().__init__(name="execution", event_bus=event_bus)
        self.plan_executor = plan_executor

    async def handle_execution_task(self, req: SubagentTaskRequestModel, plan: ExecutionPlanModel) -> SubagentTaskResultModel:
        logger.info(f"[ExecutionSubagent] Executing plan with {len(plan.steps)} steps...")
        try:
            results = await self.plan_executor.execute_plan(plan)
            res = SubagentTaskResultModel(
                task_id=req.task_id,
                correlation_id=req.correlation_id,
                subagent=self.name,
                status="completed",
                output={"results": [r.model_dump() for r in results]}
            )
        except Exception as e:
            logger.error(f"[ExecutionSubagent] Error executing plan: {e}")
            res = SubagentTaskResultModel(
                task_id=req.task_id,
                correlation_id=req.correlation_id,
                subagent=self.name,
                status="failed",
                error=str(e)
            )

        await self.publish_result(res)
        return res
