from typing import Dict, Any, List, Optional
from core.interfaces import IPlugin
from observability.logger import logger

class PluginManager:
    """Hot-loading Plugin Manager discovering, initializing, and managing plugin lifecycles."""
    
    def __init__(self, container: Any):
        self.container = container
        self._plugins: Dict[str, IPlugin] = {}

    async def load_plugin(self, plugin: IPlugin) -> None:
        name = plugin.name
        self._plugins[name] = plugin
        try:
            await plugin.on_load(self.container)
            logger.info(f"[PluginManager] Loaded plugin '{name}' v{plugin.version}")
        except Exception as e:
            logger.error(f"[PluginManager] Error loading plugin '{name}': {e}")

    async def unload_plugin(self, name: str) -> None:
        if name in self._plugins:
            try:
                await self._plugins[name].on_unload()
                logger.info(f"[PluginManager] Unloaded plugin '{name}'")
            except Exception as e:
                logger.error(f"[PluginManager] Error unloading plugin '{name}': {e}")
            del self._plugins[name]

    def list_plugins(self) -> List[Dict[str, str]]:
        return [{"name": p.name, "version": p.version} for p in self._plugins.values()]
