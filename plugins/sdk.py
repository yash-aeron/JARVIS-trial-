"""
plugins/sdk.py — JARVIS Plugin SDK & Base Development Classes.

Provides standard abstractions for building third-party JARVIS plugins:
  - PluginManifest: Defines manifest file metadata (plugin.json).
  - PluginContext: Provides SDK helper methods for registering tools, subscribing to events, and accessing container services.
  - BasePlugin: Abstract base class for third-party plugin developers.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel, Field

from core.interfaces import IPlugin, ITool, IEventBus
from tools.registry import ToolRegistry
from observability.logger import logger


class PluginManifest(BaseModel):
    """Manifest schema for third-party plugin packages (plugin.json)."""
    name:                  str
    version:               str
    description:           str           = ""
    author:                str           = "Community"
    entry_point:           str           = "plugin:Plugin"  # format: 'module_name:ClassName'
    dependencies:          List[str]     = Field(default_factory=list)
    permissions:           List[str]     = Field(default_factory=list)  # e.g., ["network", "filesystem:read", "process:launch"]
    declared_events:       List[str]     = Field(default_factory=list)  # e.g., ["weather.updated", "spotify.playback_changed"]
    declared_capabilities: List[str]     = Field(default_factory=list)  # e.g., ["get_weather", "spotify_control"]
    settings_schema:       Dict[str, Any]= Field(default_factory=dict)  # JSON-schema representation for user config


class PluginContext:
    """
    Developer-friendly context passed to plugins during on_load lifecycle.
    Encapsulates container operations so plugins don't access raw container internals directly.
    """

    def __init__(self, container: Any, manifest: PluginManifest):
        self._container = container
        self.manifest = manifest

    def register_tool(self, tool: ITool) -> None:
        """Register a custom ITool provided by this plugin."""
        tool_reg: ToolRegistry = self._container.resolve(ToolRegistry)
        tool_reg.register(tool)
        logger.info(f"[PluginSDK] Plugin '{self.manifest.name}' registered tool '{tool.metadata.name}'")

    def get_event_bus(self) -> Optional[IEventBus]:
        """Retrieve system event bus for event subscriptions."""
        try:
            return self._container.resolve(IEventBus)
        except Exception:
            return None

    def get_service(self, service_cls: Type) -> Optional[Any]:
        """Resolve a core service from DI container."""
        try:
            return self._container.resolve(service_cls)
        except Exception:
            return None


class BasePlugin(IPlugin, ABC):
    """
    Abstract Base Class for third-party JARVIS plugins.
    Developers subclass BasePlugin and implement initialize() and teardown().
    """

    def __init__(self, manifest: PluginManifest):
        self._manifest = manifest
        self.context: Optional[PluginContext] = None

    @property
    def name(self) -> str:
        return self._manifest.name

    @property
    def version(self) -> str:
        return self._manifest.version

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    async def on_load(self, container: Any) -> None:
        self.context = PluginContext(container, self._manifest)
        logger.info(f"[PluginSDK] Initializing plugin '{self.name}' v{self.version}...")
        await self.initialize(self.context)

    async def on_unload(self) -> None:
        logger.info(f"[PluginSDK] Teardown plugin '{self.name}' v{self.version}...")
        await self.teardown()

    @abstractmethod
    async def initialize(self, ctx: PluginContext) -> None:
        """Custom plugin initialization logic. Register tools, subscribe to events, etc."""
        ...

    @abstractmethod
    async def teardown(self) -> None:
        """Clean up plugin resources on shutdown or unload."""
        ...
