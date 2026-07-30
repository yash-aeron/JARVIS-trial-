"""
tools/system_tools/applications.py — Production Windows Application Launcher.

Capabilities:
  launch  — start the app (reuse existing instance by default)
  focus   — bring an existing window to the foreground
  reuse   — alias for launch with reuse_existing=True
  close   — send WM_CLOSE (graceful) then SIGTERM if still alive
  kill    — SIGKILL immediately (no grace period)
  list    — enumerate all visible windows for a process

Win32 primitives used:
  EnumWindows / EnumThreadWindows       — enumerate top-level windows
  GetWindowThreadProcessId              — map HWND → PID
  IsWindowVisible / IsIconic            — filter spurious handles
  GetWindowTextW                        — read window title
  ShowWindow(SW_RESTORE) + BringWindowToTop + SetForegroundWindow — focus
  PostMessageW(WM_CLOSE)                — graceful close request
"""

import os
import sys
import re
import time
import shutil
import asyncio
import ctypes
import ctypes.wintypes
import subprocess
import psutil
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel
from observability.logger import logger


# ── Strongly-typed observation model ──────────────────────────────────────────
class AppObservation(BaseModel):
    """Structured result returned by every ApplicationLauncherTool action."""
    app_name:       str
    action_taken:   str                      # launched | focused | closed | killed | listed | noop
    pid:            Optional[int]  = None
    executable:     str            = ""
    window_titles:  List[str]      = Field(default_factory=list)
    was_running:    bool           = False
    focused:        bool           = False
    windows_found:  int            = 0


# ── Win32 constants ────────────────────────────────────────────────────────────
SW_RESTORE      = 9
SW_SHOW         = 5
WM_CLOSE        = 0x0010
ENUM_PROC_TYPE  = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

# PID 0 is System Idle Process, 4 is the Windows kernel — never a launch target.
_PROTECTED_PIDS = {0, 4}

# Hide the shim console on Windows; harmless elsewhere.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ── Application catalog ────────────────────────────────────────────────────────
# Maps lowercase alias → (executable patterns for psutil, launch command)
_APP_CATALOG: Dict[str, Tuple[List[str], List[str]]] = {
    # alias             psutil exe patterns          spawn command
    "code":           (["code.exe"],                  ["code"]),
    "vscode":         (["code.exe"],                  ["code"]),
    "vs code":        (["code.exe"],                  ["code"]),
    "visual studio":  (["devenv.exe"],                ["devenv"]),
    "chrome":         (["chrome.exe"],                ["cmd", "/c", "start", "chrome"]),
    "google chrome":  (["chrome.exe"],                ["cmd", "/c", "start", "chrome"]),
    "edge":           (["msedge.exe"],                ["cmd", "/c", "start", "msedge"]),
    "firefox":        (["firefox.exe"],               ["cmd", "/c", "start", "firefox"]),
    "browser":        (["chrome.exe", "msedge.exe"],  ["cmd", "/c", "start", "chrome"]),
    "notepad":        (["notepad.exe"],               ["notepad.exe"]),
    "notepad++":      (["notepad++.exe"],             ["cmd", "/c", "start", "notepad++"]),
    "word":           (["winword.exe"],               ["cmd", "/c", "start", "winword"]),
    "excel":          (["excel.exe"],                 ["cmd", "/c", "start", "excel"]),
    "powerpoint":     (["powerpnt.exe"],              ["cmd", "/c", "start", "powerpnt"]),
    "outlook":        (["outlook.exe"],               ["cmd", "/c", "start", "outlook"]),
    "teams":          (["teams.exe"],                 ["cmd", "/c", "start", "teams"]),
    "slack":          (["slack.exe"],                 ["cmd", "/c", "start", "slack"]),
    "discord":        (["discord.exe"],               ["cmd", "/c", "start", "discord"]),
    "terminal":       (["wt.exe", "windowsterminal"], ["wt"]),
    "windows terminal":(["wt.exe"],                   ["wt"]),
    "cmd":            (["cmd.exe"],                   ["cmd.exe"]),
    "powershell":     (["powershell.exe", "pwsh.exe"],["powershell.exe"]),
    "pwsh":           (["pwsh.exe"],                  ["pwsh.exe"]),
    "explorer":       (["explorer.exe"],              ["explorer.exe"]),
    "file explorer":  (["explorer.exe"],              ["explorer.exe"]),
    "calculator":     (["calculatorapp.exe", "calc.exe"], ["calc.exe"]),
    "calc":           (["calculatorapp.exe", "calc.exe"], ["calc.exe"]),
    "paint":          (["mspaint.exe"],               ["mspaint.exe"]),
    "task manager":   (["taskmgr.exe"],               ["taskmgr.exe"]),
    "settings":       (["systemsettings.exe"],        ["cmd", "/c", "start", "ms-settings:"]),
    "spotify":        (["spotify.exe"],               ["cmd", "/c", "start", "spotify"]),
    "vlc":            (["vlc.exe"],                   ["cmd", "/c", "start", "vlc"]),
    "obs":            (["obs64.exe", "obs32.exe"],    ["cmd", "/c", "start", "obs64"]),
    "pycharm":        (["pycharm64.exe"],             ["cmd", "/c", "start", "pycharm64"]),
    "idea":           (["idea64.exe"],                ["cmd", "/c", "start", "idea64"]),
    "postman":        (["postman.exe"],               ["cmd", "/c", "start", "postman"]),
    "docker":         (["docker desktop.exe", "docker"],["cmd", "/c", "start", "docker desktop"]),
    "steam":          (["steam.exe"],                 ["cmd", "/c", "start", "steam"]),
    "zoom":           (["zoom.exe"],                  ["cmd", "/c", "start", "zoom"]),
    "brave":          (["brave.exe"],                 ["cmd", "/c", "start", "brave"]),
    "opera":          (["opera.exe"],                 ["cmd", "/c", "start", "opera"]),
    "snipping tool":  (["snippingtool.exe"],          ["snippingtool.exe"]),
    "control panel":  (["control.exe"],               ["control.exe"]),
}


# ── Win32 helpers (Windows-only) ──────────────────────────────────────────────
def _is_win32() -> bool:
    return sys.platform == "win32"


def _get_window_text(hwnd: int) -> str:
    if not _is_win32():
        return ""
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value.strip()


def _collect_windows(pid: int) -> List[Tuple[int, str]]:
    """Return all visible top-level HWNDs belonging to pid as (hwnd, title) pairs."""
    if not _is_win32():
        return []

    user32 = ctypes.windll.user32
    results: List[Tuple[int, str]] = []

    def _cb(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            wpid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value == pid:
                title = _get_window_text(hwnd)
                results.append((hwnd, title))
        except Exception:
            pass
        return True

    cb = ENUM_PROC_TYPE(_cb)
    user32.EnumWindows(cb, 0)
    return results


def _focus_hwnd(hwnd: int) -> bool:
    """Restore, bring to top, and set foreground for a single HWND."""
    if not _is_win32():
        return False
    try:
        user32 = ctypes.windll.user32
        # If iconic (minimized), restore first
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception as exc:
        logger.debug(f"[AppLauncher] SetForegroundWindow error: {exc}")
        return False


def _graceful_close(hwnd: int) -> None:
    """Post WM_CLOSE to window — lets the app clean up before exiting."""
    if not _is_win32():
        return
    try:
        ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    except Exception as exc:
        logger.debug(f"[AppLauncher] WM_CLOSE error: {exc}")


def _focus_window_with_title(pid: int, title_hint: Optional[str]) -> Tuple[bool, List[str]]:
    """
    Focus the best-matching window for `pid`.

    If title_hint is provided, prefer the window whose title contains it.
    Returns (focused, list_of_all_titles).
    """
    windows = _collect_windows(pid)
    if not windows:
        return False, []

    titles = [t for _, t in windows]

    # Pick best match if hint given, else first window
    target_hwnd = windows[0][0]
    if title_hint:
        hint_lower = title_hint.lower()
        for hwnd, title in windows:
            if hint_lower in title.lower():
                target_hwnd = hwnd
                break

    ok = _focus_hwnd(target_hwnd)
    return ok, titles


# ── Process lookup ─────────────────────────────────────────────────────────────
# Unknown (non-catalog) app names are matched against live process names and, on
# the spawn path, handed to cmd.exe — which re-parses shell metacharacters even
# under shell=False. Both paths require a strict, conservative name.
_SAFE_APP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+\-]*$")
_MIN_UNKNOWN_NAME_LEN = 3


def _validate_unknown_app_name(orig_name: str) -> None:
    """Reject non-catalog names that are unsafe to shell out or too broad to match on."""
    name = orig_name.strip()
    if len(name) < _MIN_UNKNOWN_NAME_LEN:
        raise ValueError(
            f"Unrecognized application name {orig_name!r} is too short to resolve safely "
            f"(minimum {_MIN_UNKNOWN_NAME_LEN} characters)."
        )
    if not _SAFE_APP_NAME.match(name):
        raise ValueError(
            f"Unrecognized application name {orig_name!r} contains unsupported characters. "
            "Only letters, digits, spaces, and . _ + - are allowed."
        )


def _match_patterns(app_lower: str) -> List[str]:
    """Resolve the psutil name patterns for an alias, validating non-catalog names."""
    if app_lower in _APP_CATALOG:
        patterns, _ = _APP_CATALOG[app_lower]
        return [p.lower() for p in patterns]
    _validate_unknown_app_name(app_lower)
    return [app_lower]


def _find_process(app_lower: str) -> Tuple[bool, Optional[int], str]:
    """
    Search running processes for one matching app_lower.

    Looks up the catalog first (exact alias), then falls back to substring
    matching against process names.

    Returns (is_running, pid, exe_name).
    """
    pat_lower = _match_patterns(app_lower)

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["pid"] in _PROTECTED_PIDS:
                continue
            pname = (proc.info["name"] or "").lower()
            for pat in pat_lower:
                if pat in pname:
                    return True, proc.info["pid"], proc.info["name"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False, None, ""


def _find_all_processes(app_lower: str) -> List[Tuple[int, str]]:
    """Return ALL running processes matching the alias (for multi-instance apps)."""
    pat_lower = _match_patterns(app_lower)
    found: List[Tuple[int, str]] = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["pid"] in _PROTECTED_PIDS:
                continue
            pname = (proc.info["name"] or "").lower()
            for pat in pat_lower:
                if pat in pname:
                    found.append((proc.info["pid"], proc.info["name"]))
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return found


# ── Spawn ──────────────────────────────────────────────────────────────────────
def _spawn_app(app_lower: str, orig_name: str) -> Optional[int]:
    """
    Launch the application using catalog command or a shell `start` fallback.
    Returns the spawned process PID (may be the shell wrapper PID on `start` commands).
    """
    if app_lower in _APP_CATALOG:
        _, cmd = _APP_CATALOG[app_lower]
        cmd = list(cmd)
        # Catalog entries name bare executables ("code"), but launchers like VS Code
        # ship as .CMD shims that Popen cannot resolve without an extension.
        if cmd[0] != "cmd":
            resolved = shutil.which(cmd[0])
            if resolved:
                cmd[0] = resolved
    else:
        _validate_unknown_app_name(orig_name)
        cmd = ["cmd", "/c", "start", "", orig_name]

    try:
        if cmd[0] == "cmd":
            # `cmd /c start` is only a launcher shim — its console must stay hidden,
            # otherwise every launch flashes a command prompt window.
            proc = subprocess.Popen(cmd, shell=False, creationflags=_NO_WINDOW)
        else:
            proc = subprocess.Popen(cmd, shell=False)
        logger.info(f"[AppLauncher] Spawned '{' '.join(cmd)}' PID={proc.pid}")
        return proc.pid
    except (FileNotFoundError, OSError) as exc:
        # Hand the executable we were asked to run to `start`, not the spoken alias:
        # "vs code" is not something Windows can resolve, but "code" is.
        target = cmd[0] if cmd[0] != "cmd" else orig_name
        if target == orig_name:
            _validate_unknown_app_name(orig_name)
        logger.info(f"[AppLauncher] Direct spawn of '{target}' failed ({exc}); retrying via start shim.")
        fallback = ["cmd", "/c", "start", "", target]
        proc = subprocess.Popen(fallback, shell=False, creationflags=_NO_WINDOW)
        logger.info(f"[AppLauncher] Fallback spawn PID={proc.pid}")
        return proc.pid


# ── ApplicationLauncherTool ────────────────────────────────────────────────────
class ApplicationLauncherTool(ITool):
    """
    Production Windows application lifecycle manager.

    Actions:
      launch  — reuse existing instance if running; spawn if absent.
      focus   — bring a running app's window to foreground.
      reuse   — alias for launch (always reuse first).
      close   — WM_CLOSE (graceful) + SIGTERM fallback after 3 s.
      kill    — SIGKILL immediately.
      list    — return all visible window titles for the process.
    """

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="app_launcher",
            description=(
                "Launch, focus, reuse, close, kill, or list windows of "
                "native Windows desktop applications."
            ),
            capabilities=["open_application", "app_automation", "launch_app",
                          "focus_window", "close_application"],
            permission_level="MEDIUM",
            args_schema={
                "app_name":    "str  — name or alias (e.g. 'VS Code', 'chrome')",
                "action":      "str  — launch | focus | reuse | close | kill | list",
                "title_hint":  "str? — substring of window title to prefer (optional)",
                "reuse":       "bool — if False, always spawn new instance (default True)",
            }
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        app_name   = request.args.get("app_name", "").strip()
        action     = request.args.get("action", "launch").strip().lower()
        title_hint = request.args.get("title_hint", None)
        reuse      = request.args.get("reuse", True)

        logger.info(
            f"[AppLauncher] action='{action}' app='{app_name}' "
            f"reuse={reuse} hint='{title_hint}' [CID: {request.correlation_id}]"
        )

        app_lower = app_name.lower().strip()
        try:
            obs = await asyncio.to_thread(self._dispatch, action, app_lower, app_name, title_hint, reuse)
        except Exception as exc:
            logger.error(f"[AppLauncher] Error: {exc}")
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error=str(exc),
            )

        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="completed",
            result=obs.model_dump(),
        )

    # ── Action dispatcher ──────────────────────────────────────────────────────
    def _dispatch(
        self,
        action: str,
        app_lower: str,
        orig_name: str,
        title_hint: Optional[str],
        reuse: bool,
    ) -> AppObservation:
        if action in ("launch", "open", "reuse"):
            return self._action_launch(app_lower, orig_name, title_hint, reuse=True)
        elif action == "focus":
            return self._action_focus(app_lower, orig_name, title_hint)
        elif action in ("close", "terminate"):
            return self._action_close(app_lower, orig_name, graceful=True)
        elif action == "kill":
            return self._action_close(app_lower, orig_name, graceful=False)
        elif action == "list":
            return self._action_list(app_lower, orig_name)
        else:
            raise ValueError(f"Unknown action '{action}'. Valid: launch, focus, reuse, close, kill, list")

    # ── launch ─────────────────────────────────────────────────────────────────
    def _action_launch(
        self,
        app_lower: str,
        orig_name: str,
        title_hint: Optional[str],
        reuse: bool = True,
    ) -> AppObservation:
        is_running, pid, exe = _find_process(app_lower)

        if is_running and pid and reuse:
            logger.info(f"[AppLauncher] '{orig_name}' running (PID {pid}) — reusing.")
            focused, titles = _focus_window_with_title(pid, title_hint)
            return AppObservation(
                app_name=orig_name,
                action_taken="focused",
                pid=pid,
                executable=exe,
                window_titles=titles,
                was_running=True,
                focused=focused,
                windows_found=len(titles),
            )

        # Not running (or reuse=False) — spawn new instance
        new_pid = _spawn_app(app_lower, orig_name)
        logger.info(f"[AppLauncher] Spawned '{orig_name}' PID={new_pid}")
        return AppObservation(
            app_name=orig_name,
            action_taken="launched",
            pid=new_pid,
            was_running=False,
        )

    # ── focus ──────────────────────────────────────────────────────────────────
    def _action_focus(
        self,
        app_lower: str,
        orig_name: str,
        title_hint: Optional[str],
    ) -> AppObservation:
        is_running, pid, exe = _find_process(app_lower)
        if not is_running or not pid:
            logger.info(f"[AppLauncher] '{orig_name}' not running — nothing to focus.")
            return AppObservation(app_name=orig_name, action_taken="noop", was_running=False)

        focused, titles = _focus_window_with_title(pid, title_hint)
        return AppObservation(
            app_name=orig_name,
            action_taken="focused",
            pid=pid,
            executable=exe,
            window_titles=titles,
            was_running=True,
            focused=focused,
            windows_found=len(titles),
        )

    # ── close / kill ───────────────────────────────────────────────────────────
    def _action_close(
        self,
        app_lower: str,
        orig_name: str,
        graceful: bool,
    ) -> AppObservation:
        procs = _find_all_processes(app_lower)
        if not procs:
            logger.info(f"[AppLauncher] '{orig_name}' not running — nothing to close.")
            return AppObservation(app_name=orig_name, action_taken="noop", was_running=False)

        closed_pids: List[int] = []
        for pid, exe in procs:
            if graceful:
                # Send WM_CLOSE to every visible window, wait up to 3 s
                windows = _collect_windows(pid)
                for hwnd, _ in windows:
                    _graceful_close(hwnd)

                deadline = time.monotonic() + 3.0
                while time.monotonic() < deadline:
                    try:
                        psutil.Process(pid).status()
                        time.sleep(0.1)
                    except psutil.NoSuchProcess:
                        break
                else:
                    # Still alive after grace period — force terminate
                    try:
                        psutil.Process(pid).terminate()
                        logger.info(f"[AppLauncher] SIGTERM PID {pid} after WM_CLOSE timeout.")
                    except psutil.NoSuchProcess:
                        pass
            else:
                try:
                    psutil.Process(pid).kill()
                except psutil.NoSuchProcess:
                    pass

            closed_pids.append(pid)
            logger.info(f"[AppLauncher] Closed '{orig_name}' PID={pid} graceful={graceful}")

        action_taken = "closed" if graceful else "killed"
        return AppObservation(
            app_name=orig_name,
            action_taken=action_taken,
            pid=closed_pids[0] if closed_pids else None,
            was_running=True,
        )

    # ── list ───────────────────────────────────────────────────────────────────
    def _action_list(self, app_lower: str, orig_name: str) -> AppObservation:
        is_running, pid, exe = _find_process(app_lower)
        if not is_running or not pid:
            return AppObservation(app_name=orig_name, action_taken="listed", was_running=False)

        windows = _collect_windows(pid)
        titles  = [t for _, t in windows if t]
        return AppObservation(
            app_name=orig_name,
            action_taken="listed",
            pid=pid,
            executable=exe,
            window_titles=titles,
            was_running=True,
            windows_found=len(windows),
        )

    # ── undo ───────────────────────────────────────────────────────────────────
    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        app_name = request.args.get("app_name", "").strip()
        action   = request.args.get("action", "launch").strip().lower()

        # Undo launch = close; undo close = nothing (can't un-close safely)
        if action in ("launch", "open", "reuse"):
            obs = await asyncio.to_thread(self._action_close, app_name.lower(), app_name, graceful=True)
        else:
            obs = AppObservation(app_name=app_name, action_taken="noop")

        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="undone",
            result=obs.model_dump(),
        )
