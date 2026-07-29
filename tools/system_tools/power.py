import psutil
from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel

class SystemControlTool(ITool):
    """System control tool for hardware metrics, process control, and system info."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="system_control",
            description="Control system settings and retrieve hardware status.",
            capabilities=["system_control", "hardware_info"],
            permission_level="LOW",
            args_schema={"action": "str"}
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        action = request.args.get("action", "get_status")
        cpu = psutil.cpu_percent(interval=None)
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
