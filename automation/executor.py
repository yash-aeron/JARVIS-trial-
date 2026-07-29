from typing import Dict, Any, Optional, List
from brain.planner import ExecutionPlanModel, PlanStepModel
from tools.registry import ToolRegistry
from automation.action_queue import ActionQueue, ActionItemModel, ActionQueueState
from automation.undo_manager import UndoManager
from state.state_manager import StateManager
from state.states import AssistantState
from core.interfaces import IEventBus, EventModel, ToolRequestModel, ToolResultModel
from observability.logger import logger

class PlanExecutor:
    """Event-driven PlanExecutor resolving capabilities dynamically via ToolRegistry."""
    
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
            
            # Capability Discovery
            matching_tools = self.tool_registry.find_by_capability(step.capability)
            if not matching_tools:
                item.state = ActionQueueState.FAILED
                item.error = f"No tools found offering capability '{step.capability}'."
                logger.error(item.error)
                res = ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error=item.error)
                results.append(res)
                break
                
            tool = matching_tools[0]  # Select primary capability tool
            tool_req = ToolRequestModel(
                request_id=item.item_id,
                correlation_id=cid,
                capability=step.capability,
                tool_name=tool.metadata.name,
                args=step.args
            )
            
            # Publish tool.started event
            if self.event_bus:
                await self.event_bus.publish(
                    EventModel(
                        correlation_id=cid,
                        topic="tool.started",
                        data={"step_id": step.step_id, "capability": step.capability, "tool": tool.metadata.name},
                        sender="PlanExecutor"
                    )
                )
                
            try:
                tool_res = await tool.execute(tool_req)
                if tool_res.status == "completed":
                    item.state = ActionQueueState.COMPLETED
                    item.result = tool_res.result
                    self.undo_manager.record(tool, tool_req, tool_res)
                else:
                    item.state = ActionQueueState.FAILED
                    item.error = tool_res.error
                    
                results.append(tool_res)
                
                # Publish tool.finished event
                if self.event_bus:
                    await self.event_bus.publish(
                        EventModel(
                            correlation_id=cid,
                            topic="tool.finished",
                            data={"step_id": step.step_id, "tool": tool.metadata.name, "status": tool_res.status, "result": tool_res.result},
                            sender="PlanExecutor"
                        )
                    )
            except Exception as e:
                item.state = ActionQueueState.FAILED
                item.error = str(e)
                logger.error(f"Step {step.step_id} failed: {e}")
                res = ToolResultModel(request_id=item.item_id, correlation_id=cid, status="failed", error=str(e))
                results.append(res)
                break
                
        self.state_manager.set_state(AssistantState.IDLE, "Execution complete", correlation_id=cid)
        return results
