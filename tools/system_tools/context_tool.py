"""
tools/system_tools/context_tool.py — Context reading as a first-class JARVIS tool.

Exposes ContextManager.get_snapshot() through the standard ITool interface so
the planner can include "read_context" as a step in any execution plan, and the
executor's ToolResultModel carries the snapshot as structured data.

The tool supports two actions:
  snapshot  — full context read (foreground, clipboard, URL, workspace)
  clipboard — clipboard only (fast, no Ctrl+C, safe everywhere)
"""
import asyncio
from typing import Optional

from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel
from context.context_manager import ContextManager, ContextSnapshotModel
from observability.logger import logger


class ContextReaderTool(ITool):
    """
    Read live desktop context: foreground app, clipboard, selected text,
    browser URL, workspace path.

    Actions:
      snapshot  — full five-signal context read.
      clipboard — clipboard only (no keypress simulation).
      selected  — clipboard + selected-text capture via Ctrl+C.
      browser   — foreground app + browser URL only.
      workspace — foreground app + workspace detection only.
    """

    def __init__(self, context_manager: Optional[ContextManager] = None):
        self._ctx = context_manager or ContextManager(capture_selected_text=False)

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="context_reader",
            description=(
                "Read live Windows desktop context: foreground application, "
                "clipboard, selected text, active browser URL, and VS Code workspace."
            ),
            capabilities=[
                "read_context", "get_clipboard", "get_selected_text",
                "get_browser_url", "get_workspace", "read_foreground_app",
            ],
            permission_level="LOW",
            args_schema={
                "action": "str  — snapshot | clipboard | selected | browser | workspace (default: snapshot)",
            },
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        action = request.args.get("action", "snapshot").strip().lower()
        logger.info(f"[ContextReaderTool] action='{action}' [CID: {request.correlation_id}]")

        loop = asyncio.get_event_loop()
        try:
            if action == "snapshot":
                self._ctx.enable_selected_text_capture(False)
                snap = await loop.run_in_executor(None, self._ctx.get_snapshot)
                data = snap.model_dump()

            elif action == "clipboard":
                from context.context_manager import _query_clipboard
                text = await loop.run_in_executor(None, _query_clipboard)
                data = {"clipboard_content": text}

            elif action == "selected":
                # Full snapshot with Ctrl+C enabled. The flag lives on a shared
                # ContextManager, so it must be restored even if the read raises —
                # otherwise later snapshots keep injecting keystrokes.
                self._ctx.enable_selected_text_capture(True)
                try:
                    snap = await loop.run_in_executor(None, self._ctx.get_snapshot)
                finally:
                    self._ctx.enable_selected_text_capture(False)
                data = {
                    "selected_text":   snap.selected_text,
                    "clipboard_content": snap.clipboard_content,
                }

            elif action == "browser":
                snap = await loop.run_in_executor(None, self._ctx.get_snapshot)
                data = {
                    "browser_url":  snap.browser_url,
                    "browser_name": snap.browser_name,
                    "window_title": snap.active_window_title,
                }

            elif action == "workspace":
                snap = await loop.run_in_executor(None, self._ctx.get_snapshot)
                data = {
                    "workspace_path": snap.workspace_path,
                    "workspace_name": snap.workspace_name,
                    "focused_app":    snap.focused_app,
                }

            else:
                return ToolResultModel(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status="failed",
                    error=f"Unknown action '{action}'. Valid: snapshot, clipboard, selected, browser, workspace",
                )

            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="completed",
                result=data,
            )

        except Exception as exc:
            logger.error(f"[ContextReaderTool] Error: {exc}")
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error=str(exc),
            )

    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        # Context reads are read-only — nothing to undo
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="undone",
            result={"note": "Context reads are non-destructive — no undo required."},
        )
