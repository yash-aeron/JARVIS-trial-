from typing import Dict, Any, Optional, List
from brain.planner import ExecutionPlan
from tools.registry import ToolRegistry
from automation.action_queue import ActionQueue, ActionItem, ActionQueueState
from automation.undo_manager import UndoManager
from state.state_manager import StateManager
from state.states import AssistantState
from core.interfaces import IEventBus, Event
from observability.logger import logger

class PlanExecutor:
    """Carries out ExecutionPlan execution step-by-step through the ActionQueue."""
    
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

    async def execute_plan(self, plan: ExecutionPlan) -> List[Dict[str, Any]]:
        self.state_manager.set_state(AssistantState.EXECUTING, f"Executing plan {plan.plan_id}")
        results = []
        
        for step in plan.steps:
            item = ActionItem(item_id=f"{plan.plan_id}_step_{step.step_id}", tool_name=step.tool_name, args=step.args)
            self.action_queue.enqueue(item)
            item.state = ActionQueueState.RUNNING
            
            tool = self.tool_registry.get(step.tool_name)
            if not tool:
                item.state = ActionQueueState.FAILED
                item.error = f"Tool '{step.tool_name}' not found."
                logger.error(item.error)
                results.append({"step_id": step.step_id, "status": "failed", "error": item.error})
                break
                
            try:
                res = await tool.execute(**step.args)
                item.state = ActionQueueState.COMPLETED
                item.result = res
                self.undo_manager.record(tool, step.args, res)
                results.append({"step_id": step.step_id, "status": "completed", "result": res})
                
                if self.event_bus:
                    await self.event_bus.publish(
                        Event(
                            topic="tool.finished",
                            data={"step_id": step.step_id, "tool": step.tool_name, "result": res},
                            sender="PlanExecutor"
                        )
                    )
            except Exception as e:
                item.state = ActionQueueState.FAILED
                item.error = str(e)
                logger.error(f"Step {step.step_id} execution failed: {e}")
                results.append({"step_id": step.step_id, "status": "failed", "error": str(e)})
                break
                
        self.state_manager.set_state(AssistantState.IDLE, "Plan execution complete")
        return results
