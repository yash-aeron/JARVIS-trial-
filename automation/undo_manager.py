from typing import Dict, List, Optional
from core.interfaces import ITool
from core.models import ToolRequestModel, ToolResultModel, UndoRecordModel
from observability.logger import logger

class UndoManager:
    """Production Undo Manager tracking execution history using typed UndoRecordModel for action reversals."""

    def __init__(self):
        self._history: List[UndoRecordModel] = []
        # Reversing an action needs the tool instance that performed it; the record
        # itself stays serializable for audit/time-travel use.
        self._tools: Dict[str, ITool] = {}

    def record(self, tool: ITool, request: ToolRequestModel, result: ToolResultModel, event_id: Optional[str] = None) -> None:
        if result.status == "completed":
            record = UndoRecordModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                tool_name=tool.metadata.name,
                capability=request.capability,
                args=dict(request.args),
                event_id=event_id
            )
            self._history.append(record)
            self._tools[request.request_id] = tool
            logger.info(f"[UndoManager] Recorded execution step '{request.request_id}' (Event: {event_id}) for undo tracking.")

    def get_history(self) -> List[UndoRecordModel]:
        return list(self._history)

    async def undo_last(self) -> Optional[ToolResultModel]:
        """Reverse the most recent recorded action. Returns None if there is nothing to undo."""
        if not self._history:
            logger.info("[UndoManager] Nothing to undo.")
            return None
        return await self._undo_record(self._history[-1])

    async def undo_correlation(self, correlation_id: str) -> List[ToolResultModel]:
        """Reverse every recorded action for a correlation ID, most recent first."""
        targets = [r for r in self._history if r.correlation_id == correlation_id]
        results: List[ToolResultModel] = []
        for record in reversed(targets):
            res = await self._undo_record(record)
            if res:
                results.append(res)
        return results

    async def _undo_record(self, record: UndoRecordModel) -> Optional[ToolResultModel]:
        tool = self._tools.get(record.request_id)
        if tool is None:
            logger.error(f"[UndoManager] No tool retained for '{record.request_id}' — cannot undo.")
            return None

        request = ToolRequestModel(
            request_id=record.request_id,
            correlation_id=record.correlation_id,
            capability=record.capability or record.tool_name,
            tool_name=record.tool_name,
            args=dict(record.args),
        )

        try:
            result = await tool.undo(request)
        except Exception as exc:
            logger.error(f"[UndoManager] Undo of '{record.request_id}' failed: {exc}")
            return ToolResultModel(
                request_id=record.request_id,
                correlation_id=record.correlation_id,
                status="failed",
                error=f"Undo failed: {exc}",
            )

        # Only forget the action once it has actually been reversed, so a failed
        # undo can be retried instead of silently dropping the record.
        self._history = [r for r in self._history if r.request_id != record.request_id]
        self._tools.pop(record.request_id, None)
        logger.info(f"[UndoManager] Undid '{record.request_id}' via tool '{record.tool_name}' (status={result.status}).")
        return result
