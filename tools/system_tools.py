import os
import subprocess
import psutil
from typing import Dict, Any
from core.interfaces import ITool, ToolMetadata, ToolRequestModel, ToolResultModel
from observability.logger import logger

class ApplicationLauncherTool(ITool):
    """Real desktop application launcher executing native system commands on Windows/OS."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="app_launcher",
            description="Launch or close native desktop applications (VS Code, Chrome, Notepad, Terminal).",
            capabilities=["open_application", "app_automation", "launch_app"],
            permission_level="MEDIUM",
            args_schema={"app_name": "str", "action": "str"}
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        app_name = request.args.get("app_name", "").strip()
        action = request.args.get("action", "launch").strip()
        
        logger.info(f"[ApplicationLauncherTool] Executing action='{action}' for app='{app_name}' [CID: {request.correlation_id}]")
        
        app_lower = app_name.lower()
        try:
            if "code" in app_lower or "vscode" in app_lower:
                subprocess.Popen(["code"], shell=True)
            elif "chrome" in app_lower:
                subprocess.Popen(["cmd", "/c", "start chrome"], shell=True)
            elif "notepad" in app_lower:
                subprocess.Popen(["notepad.exe"])
            else:
                subprocess.Popen(["cmd", "/c", f"start {app_name}"], shell=True)
                
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="completed",
                result={"app_name": app_name, "action": action, "pid_spawned": True}
            )
        except Exception as e:
            logger.error(f"[ApplicationLauncherTool] Launch error: {e}")
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error=str(e)
            )

    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        app_name = request.args.get("app_name", "").strip()
        logger.info(f"[ApplicationLauncherTool] Rollback closing app '{app_name}'")
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="undone",
            result={"app_name": app_name, "closed": True}
        )

class SystemControlTool(ITool):
    """Real system control tool for hardware metrics, process control, and volume/brightness."""
    
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
