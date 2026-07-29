"""
context/context_manager.py — Production Windows context reader.

Reads five context signals on every get_snapshot() call:

  1. Foreground application  — GetForegroundWindow → PID → psutil
  2. Clipboard               — OpenClipboard / CF_UNICODETEXT
  3. Selected text           — Ctrl+C simulation into a temp clipboard slot
  4. Browser URL             — UI Automation (IUIAutomation) address-bar search
  5. Workspace               — active VS Code workspace / working directory via
                               psutil cmdline parsing

All Win32 calls are guarded; each reader degrades independently so a failure
in one never prevents the others from running.
"""

import sys
import re
import time
import ctypes
import ctypes.wintypes
import os
import subprocess
import psutil
from typing import Optional, List, Tuple

from pydantic import BaseModel, Field
from observability.logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot model
# ─────────────────────────────────────────────────────────────────────────────
class ContextSnapshotModel(BaseModel):
    """Complete desktop context snapshot — one instance per get_snapshot() call."""

    # Foreground app
    focused_app:             str           = ""
    foreground_process_name: str           = ""
    foreground_pid:          Optional[int] = None
    active_window_title:     str           = ""

    # Clipboard
    clipboard_content:       str           = ""

    # Selected text (may equal clipboard if nothing else was selected)
    selected_text:           str           = ""

    # Browser
    browser_url:             str           = ""
    browser_name:            str           = ""

    # Workspace
    workspace_path:          str           = ""
    workspace_name:          str           = ""

    # Display
    screen_resolution:       str           = "1920x1080"

    # Assistant mode
    active_mode:             str           = "Developer"


# ─────────────────────────────────────────────────────────────────────────────
# Win32 constants
# ─────────────────────────────────────────────────────────────────────────────
CF_UNICODETEXT  = 13
WM_COPY         = 0x0301
VK_CONTROL      = 0x11
VK_C            = 0x43
KEYEVENTF_KEYUP = 0x0002

# Known browser executable names → display name
_BROWSER_EXE_MAP = {
    "chrome.exe":   "Google Chrome",
    "msedge.exe":   "Microsoft Edge",
    "firefox.exe":  "Mozilla Firefox",
    "brave.exe":    "Brave",
    "opera.exe":    "Opera",
    "vivaldi.exe":  "Vivaldi",
}

# VS Code exe names
_VSCODE_EXE = {"code.exe", "code - insiders.exe"}


def _is_win32() -> bool:
    return sys.platform == "win32"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Foreground application
# ─────────────────────────────────────────────────────────────────────────────
def _query_foreground() -> Tuple[str, str, Optional[int], str]:
    """
    Return (app_display_name, exe_name, pid, window_title).
    Falls back to safe defaults on any error.
    """
    if not _is_win32():
        return "Terminal", "python.exe", None, "JARVIS"

    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "Desktop", "explorer.exe", None, "Desktop"

        # Window title
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip() or "Desktop"

        # PID
        pid_val = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
        pid = pid_val.value or None

        exe_name = "explorer.exe"
        if pid:
            try:
                exe_name = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Friendly app name: prefer last segment after " — " or " - "
        for sep in (" — ", " - ", " – "):
            if sep in title:
                app_display = title.rsplit(sep, 1)[-1].strip()
                break
        else:
            app_display = exe_name.replace(".exe", "").capitalize()

        return app_display, exe_name, pid, title

    except Exception as exc:
        logger.debug(f"[ContextManager] Foreground query error: {exc}")
        return "Desktop", "explorer.exe", None, "Desktop"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Clipboard
# ─────────────────────────────────────────────────────────────────────────────
def _query_clipboard() -> str:
    """Read current clipboard as Unicode text (max 2000 chars)."""
    if not _is_win32():
        return ""
    try:
        user32   = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
        user32.OpenClipboard.restype = ctypes.wintypes.BOOL

        user32.IsClipboardFormatAvailable.argtypes = [ctypes.wintypes.UINT]
        user32.IsClipboardFormatAvailable.restype = ctypes.wintypes.BOOL

        user32.GetClipboardData.argtypes = [ctypes.wintypes.UINT]
        user32.GetClipboardData.restype = ctypes.wintypes.HANDLE

        kernel32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p

        kernel32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = ctypes.wintypes.BOOL

        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = ctypes.wintypes.BOOL

        if not user32.OpenClipboard(None):
            return ""
        try:
            if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return ""
            h_data = user32.GetClipboardData(CF_UNICODETEXT)
            if not h_data:
                return ""
            p_data = kernel32.GlobalLock(h_data)
            if not p_data:
                return ""
            try:
                text = ctypes.c_wchar_p(p_data).value or ""
                return text[:2000]
            finally:
                kernel32.GlobalUnlock(h_data)
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        logger.debug(f"[ContextManager] Clipboard error: {exc}")
        return ""


def _write_clipboard_unicode(text: str) -> bool:
    """Helper function to write Unicode text back to Win32 clipboard."""
    if not _is_win32() or text is None:
        return False
    try:
        user32   = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
        user32.OpenClipboard.restype = ctypes.wintypes.BOOL
        user32.EmptyClipboard.restype = ctypes.wintypes.BOOL
        user32.SetClipboardData.argtypes = [ctypes.wintypes.UINT, ctypes.wintypes.HANDLE]
        user32.SetClipboardData.restype = ctypes.wintypes.HANDLE
        user32.CloseClipboard.restype = ctypes.wintypes.BOOL

        kernel32.GlobalAlloc.argtypes = [ctypes.wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = ctypes.wintypes.BOOL

        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            if not text:
                return True
            encoded = text.encode("utf-16-le") + b"\x00\x00"
            h_mem = kernel32.GlobalAlloc(0x0002, len(encoded))  # GMEM_MOVEABLE = 0x0002
            if not h_mem:
                return False
            p_mem = kernel32.GlobalLock(h_mem)
            if not p_mem:
                return False
            try:
                ctypes.memmove(p_mem, encoded, len(encoded))
            finally:
                kernel32.GlobalUnlock(h_mem)
            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            return True
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        logger.debug(f"[ContextManager] Write clipboard error: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 3. Selected text
# ─────────────────────────────────────────────────────────────────────────────
def _query_selected_text(prior_clipboard: str) -> str:
    """
    Snapshot selected text by:
      1. Saving the current clipboard.
      2. Sending Ctrl+C to the foreground window.
      3. Reading the new clipboard value.
      4. Restoring the original clipboard.

    Returns empty string if nothing changed (no selection active).
    """
    if not _is_win32():
        return ""
    selected_result = ""
    try:
        user32 = ctypes.windll.user32

        # Send Ctrl+C keydown → keyup
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_C,       0, 0, 0)
        time.sleep(0.08)
        user32.keybd_event(VK_C,       0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.12)   # let the clipboard update

        new_clipboard = _query_clipboard()

        # Only return if the clipboard actually changed
        if new_clipboard and new_clipboard != prior_clipboard:
            selected_result = new_clipboard[:2000]
    except Exception as exc:
        logger.debug(f"[ContextManager] Selected text error: {exc}")
    finally:
        # Step 4: Restore original clipboard contents to preserve user clipboard state
        if prior_clipboard is not None:
            _write_clipboard_unicode(prior_clipboard)

    return selected_result


# ─────────────────────────────────────────────────────────────────────────────
# 4. Browser URL  (UI Automation path)
# ─────────────────────────────────────────────────────────────────────────────
def _query_browser_url(exe_name: str) -> Tuple[str, str]:
    """
    Return (url, browser_display_name) for the foreground browser window.

    Strategy:
      A) Try IUIAutomation COM to read the address bar edit control.
         Works for Chrome, Edge, Firefox without any extra permissions.
      B) Fallback: parse window title — many browsers embed the URL or page
         title in the format  "<title> - <browser name>".

    Returns ("", "") if not a browser or extraction fails.
    """
    browser_name = _BROWSER_EXE_MAP.get(exe_name.lower(), "")
    if not browser_name:
        return "", ""

    if _is_win32():
        url = _url_via_uia() or _url_via_title_parse(exe_name)
    else:
        url = ""

    return url, browser_name


def _url_via_uia() -> str:
    """
    Use Windows UI Automation to read the active browser address bar.
    Tries comtypes first (zero subprocess cost), then a PowerShell fallback.
    Both paths have strict timeout guards so they never block the snapshot.
    """
    # A) comtypes path (requires: pip install comtypes)
    try:
        import comtypes
        import comtypes.client
        # Trigger type-lib generation if needed
        uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
        )
        cond = uia.CreatePropertyCondition(30011, "addressEditBox")
        elem = uia.GetRootElement().FindFirst(4, cond)
        if elem:
            vp = elem.GetCurrentPattern(10002)
            if vp:
                return vp.Current.Value
    except Exception:
        pass

    # B) PowerShell fallback — 1.5 s hard budget, killed on timeout
    try:
        cmd = (
            "Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes; "
            "$ae=[System.Windows.Automation.AutomationElement]::RootElement; "
            "$cond=[System.Windows.Automation.PropertyCondition]::new("
            "[System.Windows.Automation.AutomationElement]::AutomationIdProperty,'addressEditBox'); "
            "$el=$ae.FindFirst('Descendants',$cond); "
            "if($el){$vp=[System.Windows.Automation.ValuePattern]::Pattern; "
            "($el.GetCurrentPattern($vp)).Current.Value}"
        )
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if _is_win32() else 0,
        )
        try:
            stdout, _ = proc.communicate(timeout=1.5)
            url = stdout.strip()
            if url and ("." in url or url.startswith("http")):
                return url
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
    except Exception:
        pass

    return ""



def _url_via_title_parse(exe_name: str) -> str:
    """
    Rough fallback: extract URL-like strings from the window title.
    Only useful when the title happens to contain the URL (rare).
    """
    try:
        user32 = ctypes.windll.user32
        hwnd   = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf    = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title  = buf.value

        # Look for http/https URLs embedded in the title
        urls = re.findall(r"https?://[^\s\"\'<>]+", title)
        if urls:
            return urls[0]
    except Exception:
        pass
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# 5. Workspace / working directory
# ─────────────────────────────────────────────────────────────────────────────
def _query_workspace(exe_name: str, pid: Optional[int], window_title: str) -> Tuple[str, str]:
    """
    Return (workspace_path, workspace_name).

    Strategies (in order):
      A) VS Code — parse --folder-uri / --file-uri flags from cmdline, or read
         the VSCODE_CWD / userDataDir from the process environment.
      B) Any editor — read the process's cwd via psutil.
      C) Parse project name from window title ("project — VS Code" pattern).
    """
    if not pid:
        return "", ""

    try:
        proc = psutil.Process(pid)
        exe_lower = exe_name.lower()

        # A) VS Code
        if exe_lower in _VSCODE_EXE:
            path = _vscode_workspace(proc, window_title)
            if path:
                return path, os.path.basename(path)

        # B) cwd of any IDE / terminal process
        try:
            cwd = proc.cwd()
            if cwd and cwd not in ("C:\\Windows\\System32", "C:\\Windows"):
                return cwd, os.path.basename(cwd)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

        # C) Title parse — "ProjectName - Editor"
        for sep in (" — ", " - ", " – "):
            if sep in window_title:
                candidate = window_title.split(sep)[0].strip()
                if candidate and len(candidate) < 60:
                    return "", candidate

    except Exception as exc:
        logger.debug(f"[ContextManager] Workspace query error: {exc}")

    return "", ""


def _vscode_workspace(proc: psutil.Process, title: str) -> str:
    """Extract VS Code workspace path from process cmdline or environment."""
    try:
        cmdline = proc.cmdline()
        for i, arg in enumerate(cmdline):
            # --folder-uri vscode-remote://... or file:///C:/...
            if arg in ("--folder-uri", "--file-uri") and i + 1 < len(cmdline):
                raw = cmdline[i + 1]
                # file:///C:/path → C:/path
                path = re.sub(r"^file:///", "", raw).replace("/", os.sep)
                if os.path.exists(path):
                    return path
            # Direct path argument
            if os.path.isdir(arg) and len(arg) > 3:
                return arg
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    # Try environment variable
    try:
        env = proc.environ()
        for key in ("VSCODE_CWD", "VSCODE_IPC_HOOK_CLI"):
            val = env.get(key, "")
            if val and os.path.isdir(val):
                return val
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    # Title: "filename.py — project — VS Code"  →  middle segment
    parts = re.split(r" [—–-] ", title)
    if len(parts) >= 2:
        candidate = parts[-2].strip()
        if candidate and "VS Code" not in candidate:
            return ""  # name only, no verified path

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Screen resolution
# ─────────────────────────────────────────────────────────────────────────────
def _query_resolution() -> str:
    if _is_win32():
        try:
            w = ctypes.windll.user32.GetSystemMetrics(0)
            h = ctypes.windll.user32.GetSystemMetrics(1)
            return f"{w}x{h}"
        except Exception:
            pass
    return "1920x1080"


# ─────────────────────────────────────────────────────────────────────────────
# ContextManager
# ─────────────────────────────────────────────────────────────────────────────
class ContextManager:
    """
    Assembles a ContextSnapshotModel from five independent Win32/psutil readers.

    Each reader is called inside its own try/except so a failure in one
    (e.g. accessibility permissions for browser URL) never blocks the others.
    """

    def __init__(self, capture_selected_text: bool = False):
        """
        Args:
            capture_selected_text: If True, simulate Ctrl+C to capture selected
                text.  Disable if JARVIS is running in a context where sending
                Ctrl+C keystrokes could cause side effects (e.g. terminal mode).
        """
        self._mode                  = "Developer"
        self._history: List[ContextSnapshotModel] = []
        self._capture_selected      = capture_selected_text

    # ── Public API ─────────────────────────────────────────────────────────────
    def get_snapshot(self) -> ContextSnapshotModel:
        """Read all context signals and return a typed snapshot."""

        # 1. Foreground app
        app_name, exe_name, pid, title = _query_foreground()

        # 2. Clipboard (read first, before Ctrl+C modifies it)
        clipboard = _query_clipboard()

        # 3. Selected text (optional — simulates Ctrl+C)
        selected = ""
        if self._capture_selected:
            selected = _query_selected_text(prior_clipboard=clipboard)

        # 4. Browser URL
        browser_url, browser_name = _query_browser_url(exe_name)

        # 5. Workspace
        workspace_path, workspace_name = _query_workspace(exe_name, pid, title)

        # 6. Resolution
        resolution = _query_resolution()

        snapshot = ContextSnapshotModel(
            focused_app=app_name,
            foreground_process_name=exe_name,
            foreground_pid=pid,
            active_window_title=title,
            clipboard_content=clipboard,
            selected_text=selected,
            browser_url=browser_url,
            browser_name=browser_name,
            workspace_path=workspace_path,
            workspace_name=workspace_name,
            screen_resolution=resolution,
            active_mode=self._mode,
        )

        self._history.append(snapshot)
        if len(self._history) > 50:
            self._history.pop(0)

        logger.debug(
            f"[ContextManager] Snapshot: app='{app_name}' pid={pid} "
            f"url='{browser_url}' workspace='{workspace_name}' "
            f"clipboard={len(clipboard)}ch selected={len(selected)}ch"
        )
        return snapshot

    def update_mode(self, mode: str) -> None:
        self._mode = mode
        logger.info(f"[ContextManager] Mode → '{mode}'")

    def get_history(self, limit: int = 10) -> List[ContextSnapshotModel]:
        return self._history[-limit:]

    def enable_selected_text_capture(self, enabled: bool = True) -> None:
        """Toggle Ctrl+C–based selected text capture at runtime."""
        self._capture_selected = enabled
        logger.info(f"[ContextManager] Selected text capture {'enabled' if enabled else 'disabled'}.")
