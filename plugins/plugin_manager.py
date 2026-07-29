"""
plugins/plugin_manager.py — Production Hot-Loading Plugin Manager.

Features:
  1. Automatic discovery of directory-based plugins in plugins/installed/ or user plugin dir.
  2. Dynamically loads manifest (plugin.json) and imports entry point module.
  3. Manages plugin lifecycles (load, unload, list, reload).
"""

import os
import sys
import json
import importlib
import importlib.util
from typing import Dict, Any, List, Optional

from core.interfaces import IPlugin
from plugins.sdk import PluginManifest, BasePlugin, PluginContext
from observability.logger import logger


class PluginManager:
    """Hot-loading Plugin Manager discovering, initializing, and managing plugin lifecycles."""

    def __init__(self, container: Any, plugin_dir: str = "plugins/installed"):
        self.container = container
        self.plugin_dir = plugin_dir
        self._plugins: Dict[str, IPlugin] = {}
        self._manifests: Dict[str, PluginManifest] = {}

    async def load_plugin(self, plugin: IPlugin) -> None:
        """Manually register and initialize an instantiated IPlugin instance."""
        name = plugin.name
        self._plugins[name] = plugin
        try:
            await plugin.on_load(self.container)
            logger.info(f"[PluginManager] Loaded plugin '{name}' v{plugin.version}")
        except Exception as e:
            logger.error(f"[PluginManager] Error loading plugin '{name}': {e}")

    async def unload_plugin(self, name: str) -> None:
        """Unloads a registered plugin and triggers its teardown callback."""
        if name in self._plugins:
            try:
                await self._plugins[name].on_unload()
                logger.info(f"[PluginManager] Unloaded plugin '{name}'")
            except Exception as e:
                logger.error(f"[PluginManager] Error unloading plugin '{name}': {e}")
            del self._plugins[name]
            if name in self._manifests:
                del self._manifests[name]

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Return list of active plugins and their versions."""
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": self._manifests[p.name].description if p.name in self._manifests else "",
                "author": self._manifests[p.name].author if p.name in self._manifests else "Built-in",
                "permissions": self._manifests[p.name].permissions if p.name in self._manifests else []
            }
            for p in self._plugins.values()
        ]

    def verify_permission_gate(self, plugin_name: str, required_permission: str) -> bool:
        """Permission-gate check: verifies if a plugin manifest declares a required capability/permission."""
        if plugin_name not in self._manifests:
            logger.warning(f"[PluginManager] Permission check failed: unknown plugin '{plugin_name}'")
            return False

        declared_perms = self._manifests[plugin_name].permissions
        # Grant if exact permission or wildcard '*' is declared
        if required_permission in declared_perms or "*" in declared_perms:
            return True

        logger.warning(f"[PluginManager] Permission denied for plugin '{plugin_name}': requested '{required_permission}', declared {declared_perms}")
        return False

    async def discover_and_load_all(self, directory: Optional[str] = None) -> List[str]:
        """
        Scans a directory for valid third-party plugins containing plugin.json manifests
        and dynamically loads them.
        """
        target_dir = directory or self.plugin_dir
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            return []

        loaded_names: List[str] = []
        for entry in os.listdir(target_dir):
            plugin_folder = os.path.join(target_dir, entry)
            manifest_file = os.path.join(plugin_folder, "plugin.json")

            if os.path.isdir(plugin_folder) and os.path.isfile(manifest_file):
                try:
                    plugin_instance = self._load_plugin_from_dir(plugin_folder, manifest_file)
                    if plugin_instance:
                        await self.load_plugin(plugin_instance)
                        self._manifests[plugin_instance.name] = plugin_instance.manifest
                        loaded_names.append(plugin_instance.name)
                except Exception as exc:
                    logger.error(f"[PluginManager] Failed to load plugin from '{plugin_folder}': {exc}")

        return loaded_names

    def _load_plugin_from_dir(self, plugin_folder: str, manifest_file: str) -> Optional[BasePlugin]:
        """Dynamically imports entry point module specified in plugin.json."""
        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        manifest = PluginManifest(**data)

        if ":" not in manifest.entry_point:
            raise ValueError(f"Invalid entry_point format '{manifest.entry_point}'. Expected 'module_name:ClassName'")

        module_name, class_name = manifest.entry_point.split(":", 1)

        # Add plugin directory to sys.path if not present
        if plugin_folder not in sys.path:
            sys.path.insert(0, plugin_folder)

        spec = importlib.util.spec_from_file_location(
            f"jarvis_plugin_{manifest.name}",
            os.path.join(plugin_folder, f"{module_name}.py")
        )
        if not spec or not spec.loader:
            raise ImportError(f"Could not load spec for '{module_name}.py' in {plugin_folder}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        plugin_cls = getattr(module, class_name, None)
        if not plugin_cls or not issubclass(plugin_cls, BasePlugin):
            raise TypeError(f"Class '{class_name}' in '{module_name}.py' is not a subclass of BasePlugin")

        plugin_instance = plugin_cls(manifest)
        return plugin_instance
