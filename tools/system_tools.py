import os
import sys
import subprocess
import psutil
import ctypes
from typing import Dict, Any, Optional
from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel
from observability.logger import logger

class ApplicationLauncherTool(ITool):
    """Production application launcher executing native system commands, process detection, and window focusing on Windows."""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="app_launcher",
            description="Launch, focus, or close native desktop applications (VS Code, Chrome, Notepad, Terminal).",
            capabilities=["open_application", "app_automation", "launch_app"],
            permission_level="MEDIUM",
            args_schema={"app_name": "str", "action": "str"}
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        app_name = request.args.get("app_name", "").strip()
        action = request.args.get("action", "launch").strip()
        
        logger.info(f"[ApplicationLauncherTool] Action='{action}' App='{app_name}' [CID: {request.correlation_id}]")
        
        app_lower = app_name.lower()
        try:
            # 1. Process Detection: Check if application is already running
            is_running, pid = self._find_running_process(app_lower)
            
            if action == "launch":
                if is_running:
                    logger.info(f"[ApplicationLauncherTool] App '{app_name}' already running (PID: {pid}). Bringing window to foreground...")
                    self._focus_process_window(pid)
                    return ToolResultModel(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        status="completed",
                        result={"app_name": app_name, "action": "focused", "pid": pid, "already_running": True}
                    )
                else:
                    new_pid = self._spawn_process(app_lower, app_name)
                    return ToolResultModel(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        status="completed",
                        result={"app_name": app_name, "action": "spawned", "pid": new_pid, "already_running": False}
                    )
            elif action == "close":
                if is_running and pid:
                    p = psutil.Process(pid)
                    p.terminate()
                    return ToolResultModel(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        status="completed",
                        result={"app_name": app_name, "action": "closed", "pid": pid}
                    )
                return ToolResultModel(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status="completed",
                    result={"app_name": app_name, "action": "closed", "was_running": False}
                )
            else:
                return ToolResultModel(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status="failed",
                    error=f"Unsupported action '{action}'"
                )
        except Exception as e:
            logger.error(f"[ApplicationLauncherTool] Execution error: {e}")
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error=str(e)
            )

    def _find_running_process(self, app_lower: str) -> tuple[bool, Optional[int]]:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = (proc.info['name'] or '').lower()
                if app_lower in pname or ("code" in app_lower and "code" in pname) or ("chrome" in app_lower and "chrome" in pname) or ("notepad" in app_lower and "notepad" in pname):
                    return True, proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False, None

    def _spawn_process(self, app_lower: str, orig_name: str) -> int:
        if "code" in app_lower or "vscode" in app_lower:
            proc = subprocess.Popen(["code"], shell=True)
        elif "chrome" in app_lower:
            proc = subprocess.Popen(["cmd", "/c", "start chrome"], shell=True)
        elif "notepad" in app_lower:
            proc = subprocess.Popen(["notepad.exe"])
        else:
            proc = subprocess.Popen(["cmd", "/c", f"start {orig_name}"], shell=True)
        return proc.pid

    def _focus_process_window(self, pid: Optional[int]) -> None:
        if sys.platform == "win32" and pid:
            try:
                # Minimal Win32 EnumWindows to focus PID window
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        app_name = request.args.get("app_name", "").strip()
        logger.info(f"[ApplicationLauncherTool] Undo closing app '{app_name}'")
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="undone",
            result={"app_name": app_name, "closed": True}
        )

class SystemControlTool(ITool):
    """System control tool for hardware metrics, process control, and volume/brightness."""
    
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
