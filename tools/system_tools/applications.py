import os
import sys
import subprocess
import psutil
import ctypes
from typing import Dict, Any, Optional, Tuple, List
from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel
from observability.logger import logger

class ApplicationLauncherTool(ITool):
    """Production application launcher executing native system commands, process detection, and Win32 window focusing."""
    
    APP_EXECUTABLE_MAP: Dict[str, List[str]] = {
        "code": ["code.exe", "code"],
        "vscode": ["code.exe", "code"],
        "chrome": ["chrome.exe", "google chrome"],
        "browser": ["chrome.exe", "msedge.exe"],
        "notepad": ["notepad.exe", "notepad"],
        "terminal": ["wt.exe", "cmd.exe", "powershell.exe"],
        "cmd": ["cmd.exe"],
        "explorer": ["explorer.exe"]
    }

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="app_launcher",
            description="Launch, focus, or close native desktop applications (VS Code, Chrome, Notepad, Terminal, Explorer).",
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
            # 1. Process Detection: Query system processes via psutil
            is_running, pid, exe_name = self._find_running_process(app_lower)
            
            if action in ["launch", "open", "focus"]:
                if is_running and pid:
                    logger.info(f"[ApplicationLauncherTool] App '{app_name}' running (PID: {pid}). Focusing window...")
                    focused = self._focus_process_window(pid)
                    return ToolResultModel(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        status="completed",
                        result={
                            "app_name": app_name,
                            "action": "focused",
                            "pid": pid,
                            "executable": exe_name,
                            "already_running": True,
                            "focused_window": focused
                        }
                    )
                else:
                    new_pid = self._spawn_process(app_lower, app_name)
                    return ToolResultModel(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        status="completed",
                        result={
                            "app_name": app_name,
                            "action": "spawned",
                            "pid": new_pid,
                            "already_running": False
                        }
                    )
            elif action in ["close", "terminate", "kill"]:
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
                    error=f"Unsupported application launcher action '{action}'"
                )
        except Exception as e:
            logger.error(f"[ApplicationLauncherTool] Execution error: {e}")
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error=str(e)
            )

    def _find_running_process(self, app_lower: str) -> Tuple[bool, Optional[int], str]:
        patterns = self.APP_EXECUTABLE_MAP.get(app_lower, [app_lower])
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = (proc.info['name'] or '').lower()
                for pat in patterns:
                    if pat in pname or app_lower in pname:
                        return True, proc.info['pid'], proc.info['name']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False, None, ""

    def _spawn_process(self, app_lower: str, orig_name: str) -> int:
        if any(k in app_lower for k in ["code", "vscode"]):
            proc = subprocess.Popen(["code"], shell=True)
        elif "chrome" in app_lower:
            proc = subprocess.Popen(["cmd", "/c", "start chrome"], shell=True)
        elif "notepad" in app_lower:
            proc = subprocess.Popen(["notepad.exe"])
        elif "terminal" in app_lower or "cmd" in app_lower:
            proc = subprocess.Popen(["cmd.exe"])
        else:
            proc = subprocess.Popen(["cmd", "/c", f"start {orig_name}"], shell=True)
        return proc.pid

    def _focus_process_window(self, pid: Optional[int]) -> bool:
        if sys.platform != "win32" or not pid:
            return False
            
        try:
            user32 = ctypes.windll.user32
            target_hwnd = []

            # EnumWindows callback function type
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

            def enum_windows_callback(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    window_pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                    if window_pid.value == pid:
                        target_hwnd.append(hwnd)
                        return False  # Stop enumeration
                return True

            cb = WNDENUMPROC(enum_windows_callback)
            user32.EnumWindows(cb, 0)

            if target_hwnd:
                hwnd = target_hwnd[0]
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                return True
        except Exception as e:
            logger.debug(f"[ApplicationLauncherTool] Win32 window focus error: {e}")
            
        return False

    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        app_name = request.args.get("app_name", "").strip()
        logger.info(f"[ApplicationLauncherTool] Undo requested for app '{app_name}'")
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="undone",
            result={"app_name": app_name, "undone": True}
        )
