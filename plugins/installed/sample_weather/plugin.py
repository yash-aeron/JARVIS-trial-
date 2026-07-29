"""
Sample Third-Party Plugin: Weather Plugin for JARVIS.

Demonstrates third-party plugin development using the JARVIS Plugin SDK.
"""

from typing import Dict, Any
from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel
from plugins.sdk import BasePlugin, PluginContext
from observability.logger import logger


class WeatherTool(ITool):
    """Custom tool provided by the third-party WeatherPlugin."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="weather_tool",
            description="Get current weather conditions and forecasts for any city.",
            capabilities=["get_weather", "weather_forecast"],
            permission_level="LOW",
            args_schema={"location": "str"}
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        location = request.args.get("location", "London").strip()
        logger.info(f"[WeatherTool] Fetching weather for '{location}' [CID: {request.correlation_id}]")

        # Simulated weather data
        weather_data = {
            "location": location,
            "condition": "Partly Cloudy",
            "temperature_c": 21.5,
            "humidity_percent": 55,
            "source": "SampleWeatherPlugin v1.0.0"
        }

        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="completed",
            result=weather_data
        )

    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="undone",
            result={"note": "Weather lookups are read-only."}
        )


class WeatherPlugin(BasePlugin):
    """Sample Third-Party Plugin class registered in plugin.json."""

    async def initialize(self, ctx: PluginContext) -> None:
        logger.info(f"[{self.name}] Initializing third-party weather plugin...")
        # Register custom tool into JARVIS tool registry via SDK Context
        ctx.register_tool(WeatherTool())

    async def teardown(self) -> None:
        logger.info(f"[{self.name}] Cleaning up third-party weather plugin...")
