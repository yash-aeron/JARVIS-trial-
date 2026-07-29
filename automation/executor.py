import asyncio
from typing import Dict, Any, Optional, List, Set
from tools.registry import ToolRegistry
from automation.action_queue import ActionQueue, ActionItemModel, ActionQueueState
from automation.undo_manager import UndoManager
from state.state_manager import StateManager
from state.states import AssistantState
from core.interfaces import IEventBus
from core.models import (
    EventModel, ToolRequestModel, ToolResultModel, 
    ExecutionPlanModel, PlanStepModel,
    ToolStartedEventData, ToolFinishedEventData
)
from observability.logger import logger

class PlanExecutor:
    """Event-driven PlanExecutor providing parallel dependency-aware step execution with retries and cancellation."""
    
    def __init__(
        self, 
        tool_registry: ToolRegistry, 
        undo_manager: UndoManager,
        state_manager: StateManager,
        event_bus: Optional[IEventBus] = None
    ):
        self.tool_registry = tool_registry
        self.undo_manager = undo_manager
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.action_queue = ActionQueue()

    async def _execute_single_step(
        self, 
        step: PlanStepModel, 
        plan_id: str, 
        cid: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResultModel:
        item = ActionItemModel(
            item_id=f"{plan_id}_step_{step.step_id}",
            correlation_id=cid,
            capability=step.capability,
            args=step.args
        )
        self.action_queue.enqueue(item)
        item.state = ActionQueueState.RUNNING
        
        ranked_candidates = self.tool_registry.find_and_rank_by_capability(step.capability, context=context)
        if not ranked_candidates:
            item.state = ActionQueueState.FAILED
            item.error = f"No tools found for capability '{step.capability}'."
            return ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error=item.error)
            
        tool, score = ranked_candidates[0]
        tool_req = ToolRequestModel(
            request_id=item.item_id,
            correlation_id=cid,
            capability=step.capability,
            tool_name=tool.metadata.name,
            args=step.args,
            timeout_sec=10.0,
            max_retries=2
        )
        
        if self.event_bus:
            start_payload = ToolStartedEventData(step_id=step.step_id, capability=step.capability, tool_name=tool.metadata.name)
            await self.event_bus.publish(
                EventModel(correlation_id=cid, topic="tool.started", payload=start_payload, sender="PlanExecutor")
            )
            
        tool_res: Optional[ToolResultModel] = None
        attempts = 0
        while attempts <= tool_req.max_retries:
            attempts += 1
            try:
                tool_res = await asyncio.wait_for(tool.execute(tool_req), timeout=tool_req.timeout_sec)
                if tool_res.status == "completed":
                    break
            except asyncio.TimeoutError:
                tool_res = ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error="Execution timeout")
            except Exception as e:
                tool_res = ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error=str(e))
                
        if tool_res and tool_res.status == "completed":
            item.state = ActionQueueState.COMPLETED
            item.result = tool_res.result
            self.undo_manager.record(tool, tool_req, tool_res)
        else:
            item.state = ActionQueueState.FAILED
            item.error = tool_res.error if tool_res else "Failed execution"
            
        if self.event_bus:
            fin_payload = ToolFinishedEventData(
                step_id=step.step_id,
                tool_name=tool.metadata.name,
                status=tool_res.status if tool_res else "failed",
                result=tool_res.result if tool_res else {},
                error=tool_res.error if tool_res else None
            )
            await self.event_bus.publish(
                EventModel(correlation_id=cid, topic="tool.finished", payload=fin_payload, sender="PlanExecutor")
            )
            
        return tool_res or ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error="Unknown error")

    async def execute_plan(self, plan: ExecutionPlanModel, context: Optional[Dict[str, Any]] = None) -> List[ToolResultModel]:
        cid = plan.correlation_id
        self.state_manager.transition_to(AssistantState.EXECUTING, f"Executing plan {plan.plan_id}", correlation_id=cid)
        
        completed_step_ids: Set[int] = set()
        results: Dict[int, ToolResultModel] = {}
        pending_steps = list(plan.steps)
        
        while pending_steps:
            ready_steps = [
                s for s in pending_steps 
                if all(dep in completed_step_ids for dep in s.depends_on)
            ]
            
            if not ready_steps:
                ready_steps = [pending_steps[0]]
                
            tasks = [self._execute_single_step(step, plan.plan_id, cid, context) for step in ready_steps]
            step_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            failed = False
            for step, res in zip(ready_steps, step_results):
                pending_steps.remove(step)
                if isinstance(res, Exception):
                    results[step.step_id] = ToolResultModel(request_id=f"{plan.plan_id}_{step.step_id}", correlation_id=cid, status="failed", error=str(res))
                    failed = True
                else:
                    results[step.step_id] = res
                    if res.status == "completed":
                        completed_step_ids.add(step.step_id)
                    else:
                        failed = True
                        
            if failed:
                break
                
        self.state_manager.transition_to(AssistantState.IDLE, "Execution complete", correlation_id=cid)
        return list(results.values())
