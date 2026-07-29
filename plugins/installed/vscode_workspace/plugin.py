"""
plugins/installed/vscode_workspace/plugin.py — VS Code Workspace Reference Plugin.
"""
from typing import Dict, Any
from pydantic import BaseModel, Field
from plugins.sdk import BasePlugin, PluginContext
from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel
from observability.logger import logger


class VSCodeWorkspaceObservation(BaseModel):
    action: str
    workspace_path: str = "."
    status: str = "active"


class VSCodeWorkspaceTool(ITool):
    """ITool-conformant VS Code workspace command tool."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="vscode_workspace_tool",
            description="Manages VS Code workspace folders and command tasks",
            capabilities=["vscode_workspace", "workspace_command"],
            permission_level="LOW"
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        action = request.args.get("action", "open_folder")
        folder = request.args.get("folder", ".")
        logger.info(f"[VSCodeWorkspaceTool] Executing '{action}' on folder '{folder}'")

        obs = VSCodeWorkspaceObservation(action=action, workspace_path=folder)
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="completed",
            result=obs.model_dump()
        )

    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        logger.info(f"[VSCodeWorkspaceTool] Undoing workspace action for request '{request.request_id}'")
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="completed",
            result={"status": "undone"}
        )


class VSCodeWorkspacePlugin(BasePlugin):
    """Reference VS Code Workspace Plugin implementing BasePlugin SDK."""

    async def initialize(self, ctx: PluginContext) -> None:
        logger.info("[VSCodeWorkspacePlugin] Initializing VS Code workspace manager...")
        ctx.register_tool(VSCodeWorkspaceTool())

    async def teardown(self) -> None:
        logger.info("[VSCodeWorkspacePlugin] Teardown VS Code workspace manager.")
