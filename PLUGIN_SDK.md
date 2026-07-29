# JARVIS Plugin SDK Guide

Plugins allow third-party developers to extend JARVIS with custom tools, capabilities, UI widgets, and event hooks without modifying core code.

## Plugin Structure

```python
from core.interfaces import IPlugin, ITool, ToolMetadata
from typing import Any, Dict

class CustomPluginTool(ITool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="custom_tool",
            description="Custom plugin functionality.",
            capabilities=["custom_capability"],
            permission_level="MEDIUM",
            args_schema={"input": "str"}
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        return {"status": "success", "result": "Plugin action completed"}

    async def undo(self, **kwargs) -> Dict[str, Any]:
        return {"status": "undone"}

class SamplePlugin(IPlugin):
    @property
    def name(self) -> str:
        return "SamplePlugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def on_load(self, container: Any) -> None:
        tool_registry = container.resolve("ToolRegistry")
        tool_registry.register(CustomPluginTool())

    async def on_unload(self) -> None:
        pass
```
