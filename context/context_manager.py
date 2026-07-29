import sys
import ctypes
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from observability.logger import logger

class ContextSnapshotModel(BaseModel):
    focused_app: str = "VS Code"
    active_window_title: str = "JARVIS Workspace"
    clipboard_content: str = ""
    active_mode: str = "Developer"

class ContextManager:
    """Manages real-time transient runtime context querying real Windows foreground window title, clipboard, and active mode."""
    
    def __init__(self):
        self._mode = "Developer"

    def get_snapshot(self) -> ContextSnapshotModel:
        focused_app, title = self._query_foreground_window()
        clipboard_text = self._query_clipboard()
        
        return ContextSnapshotModel(
            focused_app=focused_app,
            active_window_title=title,
            clipboard_content=clipboard_text,
            active_mode=self._mode
        )

    def _query_foreground_window(self) -> tuple[str, str]:
        if sys.platform == "win32":
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value or "Desktop"
                app_name = title.split("-")[-1].strip() if "-" in title else title
                return app_name, title
            except Exception as e:
                logger.debug(f"[ContextManager] Error querying foreground window: {e}")
        return "VS Code", "JARVIS - Workspace"

    def _query_clipboard(self) -> str:
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.OpenClipboard(None)
                if ctypes.windll.user32.IsClipboardFormatAvailable(1):  # CF_TEXT
                    h_data = ctypes.windll.user32.GetClipboardData(1)
                    p_data = ctypes.windll.kernel32.GlobalLock(h_data)
                    text = ctypes.c_char_p(p_data).value.decode('utf-8', errors='ignore')
                    ctypes.windll.kernel32.GlobalUnlock(h_data)
                    ctypes.windll.user32.CloseClipboard()
                    return text[:200]  # First 200 chars
                ctypes.windll.user32.CloseClipboard()
            except Exception:
                pass
        return ""

    def update_mode(self, mode: str) -> None:
        self._mode = mode
