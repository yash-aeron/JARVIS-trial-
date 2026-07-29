"""
plugins/installed/spotify_control/plugin.py — Spotify Media Playback Reference Plugin.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from plugins.sdk import BasePlugin, PluginContext
from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel
from observability.logger import logger


class SpotifyPlaybackObservation(BaseModel):
    action: str
    track: str = "Unknown Track"
    artist: str = "Unknown Artist"
    is_playing: bool = True


class SpotifyTool(ITool):
    """ITool-conformant Spotify playback control tool."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="spotify_tool",
            description="Controls Spotify playback (play, pause, next, volume)",
            capabilities=["spotify_playback", "media_control"],
            permission_level="LOW"
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        action = request.args.get("action", "play")
        track = request.args.get("track", "Favorite Track")
        logger.info(f"[SpotifyTool] Executing '{action}' on track '{track}'")

        obs = SpotifyPlaybackObservation(
            action=action,
            track=track,
            artist="JARVIS Media Engine",
            is_playing=(action != "pause")
        )
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="completed",
            result=obs.model_dump()
        )


class SpotifyControlPlugin(BasePlugin):
    """Reference Spotify Playback Plugin implementing BasePlugin SDK."""

    async def initialize(self, ctx: PluginContext) -> None:
        logger.info("[SpotifyControlPlugin] Initializing Spotify controller...")
        ctx.register_tool(SpotifyTool())

    async def teardown(self) -> None:
        logger.info("[SpotifyControlPlugin] Teardown Spotify controller.")
