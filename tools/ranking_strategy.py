from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from core.interfaces import ITool
from core.models import ToolMetadata

class IRankingStrategy(ABC):
    @abstractmethod
    def rank(self, candidates: List[ITool], capability: str, context: Optional[Dict[str, Any]] = None) -> List[Tuple[ITool, float]]:
        pass

class ContextualRankingStrategy(IRankingStrategy):
    """Pluggable Tool Ranking Strategy evaluating Capability Match, Context Alignment, Permission Level, and Execution Speed."""
    
    def rank(self, candidates: List[ITool], capability: str, context: Optional[Dict[str, Any]] = None) -> List[Tuple[ITool, float]]:
        scored_candidates: List[Tuple[ITool, float]] = []
        
        focused_app = (context or {}).get("focused_app", "").lower()
        active_mode = (context or {}).get("active_mode", "Developer").lower()
        
        for tool in candidates:
            score = 0.50  # Base candidate score
            meta = tool.metadata
            
            # Primary capability specialization bonus
            if meta.capabilities and meta.capabilities[0] == capability:
                score += 0.25
                
            # Runtime context alignment (e.g. window title or focused app matching tool)
            if focused_app and (focused_app in meta.name.lower() or focused_app in meta.description.lower()):
                score += 0.15
                
            # Permission suitability
            if meta.permission_level in ["LOW", "MEDIUM"]:
                score += 0.10
            elif meta.permission_level == "HIGH":
                score += 0.05
                
            scored_candidates.append((tool, min(1.0, score)))
            
        scored_candidates.sort(key=lambda item: item[1], reverse=True)
        return scored_candidates
