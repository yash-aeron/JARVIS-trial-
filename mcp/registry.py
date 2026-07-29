from typing import Dict, Any, List
from mcp.adapters.tool_adapter import MCPToolAdapter
from observability.logger import logger

class MCPRegistry:
    """Registry for discovering and managing Model Context Protocol (MCP) servers and tools."""
    
    def __init__(self):
        self._mcp_tools: Dict[str, MCPToolAdapter] = {}

    def register_mcp_tool(self, name: str, description: str, capabilities: List[str]) -> MCPToolAdapter:
        adapter = MCPToolAdapter(mcp_name=name, mcp_desc=description, capabilities=capabilities)
        self._mcp_tools[name] = adapter
        logger.info(f"[MCPRegistry] Registered MCP Tool: '{name}'")
        return adapter

    def list_mcp_tools(self) -> List[str]:
        return list(self._mcp_tools.keys())
