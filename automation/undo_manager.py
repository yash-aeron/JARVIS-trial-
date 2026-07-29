from typing import List, Optional
from core.interfaces import ITool
from core.models import ToolRequestModel, ToolResultModel, UndoRecordModel
from observability.logger import logger

class UndoManager:
    """Production Undo Manager tracking execution history using typed UndoRecordModel for action reversals."""
    
    def __init__(self):
        self._history: List[UndoRecordModel] = []

    def record(self, tool: ITool, request: ToolRequestModel, result: ToolResultModel) -> None:
        if result.status == "completed":
            record = UndoRecordModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                tool_name=tool.metadata.name
            )
            self._history.append(record)
            logger.info(f"[UndoManager] Recorded execution step '{request.request_id}' for undo tracking.")

    def get_history(self) -> List[UndoRecordModel]:
        return list(self._history)
