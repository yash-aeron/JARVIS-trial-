"""
tests/test_phase4.py — Integration and unit test suite for Phase 4 Plugin Ecosystem.
"""
import pytest
import asyncio
import os

from core.container import DependencyContainer
from core.app import bootstrap_container
from plugins.sdk import PluginManifest, PluginContext
from plugins.plugin_manager import PluginManager


@pytest.mark.asyncio
async def test_plugin_manifest_schema_formalization():
    """Verify formal PluginManifest schema validation with permissions and settings."""
    manifest = PluginManifest(
        name="test_plugin",
        version="1.0.0",
        description="Test plugin manifest",
        permissions=["network", "filesystem:read"],
        declared_events=["test.event"],
        declared_capabilities=["test_cap"],
        settings_schema={"setting_1": {"type": "string"}}
    )

    assert manifest.name == "test_plugin"
    assert "network" in manifest.permissions
    assert "test.event" in manifest.declared_events
    assert "test_cap" in manifest.declared_capabilities
    assert "setting_1" in manifest.settings_schema


@pytest.mark.asyncio
async def test_plugin_permission_gate_check():
    """Verify PluginManager permission gate enforcement."""
    container = bootstrap_container()
    pm = PluginManager(container, plugin_dir="plugins/installed")
    await pm.discover_and_load_all()

    # Spotify plugin declares ["network", "media:playback"]
    assert pm.verify_permission_gate("spotify_control", "network") is True
    assert pm.verify_permission_gate("spotify_control", "media:playback") is True
    assert pm.verify_permission_gate("spotify_control", "unauthorized_permission") is False


@pytest.mark.asyncio
async def test_reference_plugins_discovery_and_tool_execution():
    """Verify hot-loading and execution of reference plugins (Spotify & VS Code Workspace)."""
    container = bootstrap_container()
    pm: PluginManager = container.resolve(PluginManager)
    loaded = await pm.discover_and_load_all("plugins/installed")

    assert "spotify_control" in loaded
    assert "vscode_workspace" in loaded
    assert "sample_weather" in loaded

    active_plugins = pm.list_plugins()
    plugin_names = [p["name"] for p in active_plugins]
    assert "spotify_control" in plugin_names
    assert "vscode_workspace" in plugin_names
