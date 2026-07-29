from typing import Dict, Any
from core.interfaces import ITool, ToolMetadata
from observability.logger import logger

class SystemControlTool(ITool):
    """System control tool for volume, brightness, hardware controls."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="system_control",
            description="Control system hardware settings like volume, mute, and display brightness.",
            capabilities=["system_control", "volume_control"],
            permission_level="MEDIUM",
            args_schema={"action": "str", "value": "optional int"}
        )

    async def execute(self, action: str = "get_status", value: Any = None, **kwargs) -> Dict[str, Any]:
        logger.info(f"[SystemControlTool] Executing action='{action}', value='{value}'")
        return {"status": "success", "action": action, "value": value}

    async def undo(self, **kwargs) -> Dict[str, Any]:
        return {"status": "undone", "message": "System control reverted."}

class ApplicationLauncherTool(ITool):
    """Launches desktop applications like VS Code, Chrome, Terminal."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="app_launcher",
            description="Launch or close desktop applications by name.",
            capabilities=["app_automation", "launch_app"],
            permission_level="MEDIUM",
            args_schema={"app_name": "str", "action": "str"}
        )

    async def execute(self, app_name: str = "", action: str = "launch", **kwargs) -> Dict[str, Any]:
        logger.info(f"[ApplicationLauncherTool] {action} app '{app_name}'")
        return {"status": "success", "app_name": app_name, "action": action}

    async def undo(self, app_name: str = "", **kwargs) -> Dict[str, Any]:
        return {"status": "undone", "message": f"Closed application {app_name}."}
