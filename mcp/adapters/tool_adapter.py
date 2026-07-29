from typing import Dict, Any, List
from core.interfaces import ITool, ToolMetadata
from observability.logger import logger

class MCPToolAdapter(ITool):
    """Adapts an external Model Context Protocol (MCP) tool into standard JARVIS ITool interface."""
    
    def __init__(self, mcp_name: str, mcp_desc: str, capabilities: List[str]):
        self._name = f"mcp_{mcp_name}"
        self._desc = mcp_desc
        self._capabilities = capabilities

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self._name,
            description=self._desc,
            capabilities=self._capabilities,
            permission_level="MEDIUM",
            args_schema={"params": "dict"}
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        logger.info(f"[MCPToolAdapter] Executing MCP tool '{self._name}' with kwargs: {kwargs}")
        return {"status": "success", "mcp_tool": self._name, "output": "MCP execution completed."}

    async def undo(self, **kwargs) -> Dict[str, Any]:
        return {"status": "undone", "mcp_tool": self._name}
