from typing import Dict, Any, List, Optional
from core.interfaces import ITool, ToolMetadata, ToolRequestModel, ToolResultModel
from observability.logger import logger

class ToolRegistry:
    """Registry managing strongly-typed tools with Capability Discovery support."""
    
    def __init__(self):
        self._tools: Dict[str, ITool] = {}
        self._capabilities_map: Dict[str, List[ITool]] = {}

    def register(self, tool: ITool) -> None:
        meta = tool.metadata
        self._tools[meta.name] = tool
        
        for cap in meta.capabilities:
            if cap not in self._capabilities_map:
                self._capabilities_map[cap] = []
            if tool not in self._capabilities_map[cap]:
                self._capabilities_map[cap].append(tool)
                
        logger.info(f"Registered tool '{meta.name}' [Capabilities: {', '.join(meta.capabilities)}]")

    def get(self, name: str) -> Optional[ITool]:
        return self._tools.get(name)

    def find_by_capability(self, capability: str) -> List[ITool]:
        """Capability Discovery mechanism decoupling tool names from intent/planner."""
        return self._capabilities_map.get(capability, [])

    def list_all(self) -> List[Dict[str, Any]]:
        return [
            t.metadata.model_dump()
            for t in self._tools.values()
        ]
