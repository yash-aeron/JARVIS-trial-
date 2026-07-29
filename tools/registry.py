from typing import Dict, Any, List, Optional, Tuple
from core.interfaces import ITool
from core.models import ToolMetadata
from observability.logger import logger

class ToolRegistry:
    """Registry managing strongly-typed tools with ranked Capability Discovery scoring."""
    
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
        return self._capabilities_map.get(capability, [])

    def find_and_rank_by_capability(self, capability: str, context: Optional[Dict[str, Any]] = None) -> List[Tuple[ITool, float]]:
        """Ranks candidate tools for a capability by matching score, permission suitability, and specialization."""
        candidates = self._capabilities_map.get(capability, [])
        scored_candidates: List[Tuple[ITool, float]] = []
        
        for tool in candidates:
            score = 0.5  # Base candidate score
            meta = tool.metadata
            
            # Exact primary capability specialization bonus
            if meta.capabilities and meta.capabilities[0] == capability:
                score += 0.3
                
            # Permission score adjustment (LOW/MEDIUM preferred for safety)
            if meta.permission_level in ["LOW", "MEDIUM"]:
                score += 0.15
            elif meta.permission_level == "HIGH":
                score += 0.05
                
            scored_candidates.append((tool, min(1.0, score)))
            
        scored_candidates.sort(key=lambda item: item[1], reverse=True)
        return scored_candidates

    def list_all(self) -> List[Dict[str, Any]]:
        return [t.metadata.model_dump() for t in self._tools.values()]
