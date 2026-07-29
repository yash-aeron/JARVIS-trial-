from typing import Dict, Any, List, Optional, Tuple
from core.interfaces import ITool
from core.models import ToolMetadata
from tools.ranking_strategy import IRankingStrategy, ContextualRankingStrategy
from observability.logger import logger

class ToolRegistry:
    """Registry managing strongly-typed tools with pluggable Ranking Strategy for Capability Discovery."""
    
    def __init__(self, ranking_strategy: Optional[IRankingStrategy] = None):
        self._tools: Dict[str, ITool] = {}
        self._capabilities_map: Dict[str, List[ITool]] = {}
        self.ranking_strategy = ranking_strategy or ContextualRankingStrategy()

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
        candidates = self._capabilities_map.get(capability, [])
        return self.ranking_strategy.rank(candidates, capability, context)

    def list_all(self) -> List[Dict[str, Any]]:
        return [t.metadata.model_dump() for t in self._tools.values()]
