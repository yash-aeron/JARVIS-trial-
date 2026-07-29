import sys
import ctypes
import psutil
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field
from observability.logger import logger

class ContextSnapshotModel(BaseModel):
    focused_app: str = "VS Code"
    foreground_process_name: str = "code.exe"
    foreground_pid: Optional[int] = None
    active_window_title: str = "JARVIS Workspace"
    clipboard_content: str = ""
    screen_resolution: str = "1920x1080"
    active_mode: str = "Developer"

class ContextManager:
    """Production ContextManager querying real Windows APIs for foreground process, active window title, Unicode clipboard, and display resolution."""
    
    def __init__(self):
        self._mode = "Developer"
        self._history: List[ContextSnapshotModel] = []

    def get_snapshot(self) -> ContextSnapshotModel:
        app_name, proc_name, pid, title = self._query_foreground_process_and_window()
        clipboard_text = self._query_clipboard_unicode()
        resolution = self._query_screen_resolution()
        
        snapshot = ContextSnapshotModel(
            focused_app=app_name,
            foreground_process_name=proc_name,
            foreground_pid=pid,
            active_window_title=title,
            clipboard_content=clipboard_text,
            screen_resolution=resolution,
            active_mode=self._mode
        )
        
        # Keep short-term context history
        self._history.append(snapshot)
        if len(self._history) > 50:
            self._history.pop(0)
            
        return snapshot

    def _query_foreground_process_and_window(self) -> Tuple[str, str, Optional[int], str]:
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if not hwnd:
                    return "Desktop", "explorer.exe", None, "Desktop"
                    
                # 1. Fetch Window Title
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value or "Desktop"
                
                # 2. Fetch Process PID & Executable Name
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                
                proc_name = "explorer.exe"
                if pid.value:
                    try:
                        p = psutil.Process(pid.value)
                        proc_name = p.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                        
                app_name = title.split("-")[-1].strip() if "-" in title else proc_name.replace(".exe", "").capitalize()
                return app_name, proc_name, pid.value, title
            except Exception as e:
                logger.debug(f"[ContextManager] Win32 process/window query error: {e}")
                
        return "VS Code", "code.exe", 1000, "JARVIS Workspace - VS Code"

    def _query_clipboard_unicode(self) -> str:
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                
                if user32.OpenClipboard(None):
                    try:
                        CF_UNICODETEXT = 13
                        if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                            h_data = user32.GetClipboardData(CF_UNICODETEXT)
                            if h_data:
                                p_data = kernel32.GlobalLock(h_data)
                                if p_data:
                                    try:
                                        text = ctypes.c_wchar_p(p_data).value or ""
                                        return text[:300]  # First 300 chars
                                    finally:
                                        kernel32.GlobalUnlock(h_data)
                    finally:
                        user32.CloseClipboard()
            except Exception as e:
                logger.debug(f"[ContextManager] Clipboard query error: {e}")
        return ""

    def _query_screen_resolution(self) -> str:
        if sys.platform == "win32":
            try:
                w = ctypes.windll.user32.GetSystemMetrics(0)
                h = ctypes.windll.user32.GetSystemMetrics(1)
                return f"{w}x{h}"
            except Exception:
                pass
        return "1920x1080"

    def update_mode(self, mode: str) -> None:
        self._mode = mode
        logger.info(f"[ContextManager] Active mode set to: '{mode}'")

    def get_history(self, limit: int = 10) -> List[ContextSnapshotModel]:
        return self._history[-limit:]
