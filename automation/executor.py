import asyncio
from typing import Dict, Any, Optional, List
from brain.planner import ExecutionPlanModel, PlanStepModel
from tools.registry import ToolRegistry
from automation.action_queue import ActionQueue, ActionItemModel, ActionQueueState
from automation.undo_manager import UndoManager
from state.state_manager import StateManager
from state.states import AssistantState
from core.interfaces import IEventBus
from core.models import (
    EventModel, ToolRequestModel, ToolResultModel, 
    ToolStartedEventData, ToolFinishedEventData
)
from observability.logger import logger

class PlanExecutor:
    """Event-driven PlanExecutor resolving ranked capability tools with timeouts and retries."""
    
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

    async def execute_plan(self, plan: ExecutionPlanModel) -> List[ToolResultModel]:
        cid = plan.correlation_id
        self.state_manager.set_state(AssistantState.EXECUTING, f"Executing plan {plan.plan_id}", correlation_id=cid)
        results: List[ToolResultModel] = []
        
        for step in plan.steps:
            item = ActionItemModel(
                item_id=f"{plan.plan_id}_step_{step.step_id}",
                correlation_id=cid,
                capability=step.capability,
                args=step.args
            )
            self.action_queue.enqueue(item)
            item.state = ActionQueueState.RUNNING
            
            # Ranked Capability Discovery
            ranked_candidates = self.tool_registry.find_and_rank_by_capability(step.capability)
            if not ranked_candidates:
                item.state = ActionQueueState.FAILED
                item.error = f"No candidate tools found for capability '{step.capability}'."
                logger.error(item.error)
                res = ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error=item.error)
                results.append(res)
                break
                
            tool, score = ranked_candidates[0]  # Highest ranked tool
            logger.info(f"Selected tool '{tool.metadata.name}' for capability '{step.capability}' [Rank Score: {score:.2f}]")
            
            tool_req = ToolRequestModel(
                request_id=item.item_id,
                correlation_id=cid,
                capability=step.capability,
                tool_name=tool.metadata.name,
                args=step.args,
                timeout_sec=10.0,
                max_retries=2
            )
            
            # Emit ToolStartedEventData payload
            if self.event_bus:
                start_data = ToolStartedEventData(step_id=step.step_id, capability=step.capability, tool_name=tool.metadata.name)
                await self.event_bus.publish(
                    EventModel(
                        correlation_id=cid,
                        topic="tool.started",
                        data=start_data.model_dump(),
                        sender="PlanExecutor"
                    )
                )
                
            # Execution with Retry & Timeout logic
            tool_res: Optional[ToolResultModel] = None
            attempts = 0
            while attempts <= tool_req.max_retries:
                attempts += 1
                try:
                    tool_res = await asyncio.wait_for(tool.execute(tool_req), timeout=tool_req.timeout_sec)
                    if tool_res.status == "completed":
                        break
                except asyncio.TimeoutError:
                    logger.warning(f"Step {step.step_id} execution timed out (Attempt {attempts}/{tool_req.max_retries + 1})")
                    tool_res = ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error="Execution timeout")
                except Exception as e:
                    logger.warning(f"Step {step.step_id} failed with error: {e} (Attempt {attempts}/{tool_req.max_retries + 1})")
                    tool_res = ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error=str(e))
                    
            if tool_res and tool_res.status == "completed":
                item.state = ActionQueueState.COMPLETED
                item.result = tool_res.result
                self.undo_manager.record(tool, tool_req, tool_res)
            else:
                item.state = ActionQueueState.FAILED
                item.error = tool_res.error if tool_res else "Execution failed"
                
            results.append(tool_res or ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error="Unknown execution error"))
            
            # Emit ToolFinishedEventData payload
            if self.event_bus:
                fin_data = ToolFinishedEventData(
                    step_id=step.step_id,
                    tool_name=tool.metadata.name,
                    status=tool_res.status if tool_res else "failed",
                    result=tool_res.result if tool_res else {},
                    error=tool_res.error if tool_res else None
                )
                await self.event_bus.publish(
                    EventModel(
                        correlation_id=cid,
                        topic="tool.finished",
                        data=fin_data.model_dump(),
                        sender="PlanExecutor"
                    )
                )
                
            if item.state == ActionQueueState.FAILED:
                break
                
        self.state_manager.set_state(AssistantState.IDLE, "Execution complete", correlation_id=cid)
        return results
