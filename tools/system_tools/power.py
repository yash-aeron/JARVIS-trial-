import asyncio
import psutil
from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel

# Read-only actions this tool actually implements. Power-state changes (shutdown,
# restart, sleep, lock, ...) are deliberately not implemented — reporting them as
# completed would make the assistant claim it did something it never did.
_STATUS_ACTIONS = {"get_status", "status", "hardware_info", "get_metrics"}


class SystemControlTool(ITool):
    """System control tool for hardware metrics, process control, and system info."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="system_control",
            description="Control system settings and retrieve hardware status.",
            capabilities=["system_control", "hardware_info"],
            permission_level="LOW",
            args_schema={"action": "str  — get_status (hardware metrics)"}
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        action = str(request.args.get("action") or "get_status").strip().lower()

        if action not in _STATUS_ACTIONS:
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error=(
                    f"Action '{action}' is not supported by system_control. "
                    f"Supported: {', '.join(sorted(_STATUS_ACTIONS))}."
                ),
            )

        # cpu_percent(interval=None) returns 0.0 on its first call in a process;
        # a short blocking sample gives a real reading, so keep it off the loop.
        cpu = await asyncio.to_thread(psutil.cpu_percent, 0.1)
        memory = psutil.virtual_memory()

        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="completed",
            result={
                "action": action,
                "cpu_percent": cpu,
                "ram_percent": memory.percent
            }
        )

    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="undone",
            result={"message": "System state unchanged"}
        )
