from typing import List, Dict, Any
from core.interfaces import ITool
from observability.logger import logger

class UndoManager:
    """Action Undo & Rollback transaction history manager."""
    
    def __init__(self):
        self._history: List[Dict[str, Any]] = []

    def record(self, tool: ITool, kwargs: Dict[str, Any], result: Dict[str, Any]) -> None:
        self._history.append({
            "tool": tool,
            "kwargs": kwargs,
            "result": result
        })
        logger.debug(f"[UndoManager] Recorded action for tool '{tool.metadata.name}'")

    async def rollback_last(self) -> Dict[str, Any]:
        if not self._history:
            return {"status": "error", "message": "No actions available to undo."}
            
        last_item = self._history.pop()
        tool: ITool = last_item["tool"]
        kwargs: Dict[str, Any] = last_item["kwargs"]
        
        logger.info(f"[UndoManager] Rolling back action for tool '{tool.metadata.name}'")
        undo_res = await tool.undo(**kwargs)
        return undo_res
