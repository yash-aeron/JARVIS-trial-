from typing import List, Dict, Any
from core.interfaces import ITool, ToolRequestModel, ToolResultModel
from observability.logger import logger

class UndoManager:
    """Action Undo & Rollback transaction history manager."""
    
    def __init__(self):
        self._history: List[Dict[str, Any]] = []

    def record(self, tool: ITool, request: ToolRequestModel, result: ToolResultModel) -> None:
        self._history.append({
            "tool": tool,
            "request": request,
            "result": result
        })
        logger.debug(f"[UndoManager] Recorded action for tool '{tool.metadata.name}' [CID: {request.correlation_id}]")

    async def rollback_last(self) -> ToolResultModel:
        if not self._history:
            return ToolResultModel(
                request_id="none",
                correlation_id="none",
                status="failed",
                error="No recorded actions to undo."
            )
            
        last_item = self._history.pop()
        tool: ITool = last_item["tool"]
        request: ToolRequestModel = last_item["request"]
        
        logger.info(f"[UndoManager] Rolling back action for tool '{tool.metadata.name}'")
        undo_res = await tool.undo(request)
        return undo_res
