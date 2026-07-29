from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from core.interfaces import ITool
from core.models import ToolMetadata, ExecutionContextModel

class IRankingStrategy(ABC):
    @abstractmethod
    def rank(self, candidates: List[ITool], capability: str, context: Optional[ExecutionContextModel] = None) -> List[Tuple[ITool, float]]:
        """Ranks candidate tools based on capability match, context alignment, and strategy scoring."""
        ...

class ContextAwareRankingStrategy(IRankingStrategy):
    """Evaluates tool relevance against active runtime context (focused window/app)."""
    
    def rank(self, candidates: List[ITool], capability: str, context: Optional[ExecutionContextModel] = None) -> List[Tuple[ITool, float]]:
        focused_app = (context.focused_app if context else "").lower()
        results: List[Tuple[ITool, float]] = []
        for tool in candidates:
            score = 0.5
            if focused_app and (focused_app in tool.metadata.name.lower() or focused_app in tool.metadata.description.lower()):
                score += 0.3
            results.append((tool, min(1.0, score)))
        return results

class CompositeRankingStrategy(IRankingStrategy):
    """Production Multi-Strategy Evaluator combining Context, Permission Level, Performance Speed, and Historical Success Rate."""
    
    def __init__(self, historical_success_map: Optional[Dict[str, float]] = None):
        self.historical_success_map = historical_success_map or {}

    def rank(self, candidates: List[ITool], capability: str, context: Optional[ExecutionContextModel] = None) -> List[Tuple[ITool, float]]:
        scored_candidates: List[Tuple[ITool, float]] = []
        focused_app = (context.focused_app if context else "").lower()
        
        for tool in candidates:
            score = 0.40  # Base score
            meta = tool.metadata
            
            # 1. Primary capability specialization
            if meta.capabilities and meta.capabilities[0] == capability:
                score += 0.25
                
            # 2. Runtime Context alignment
            if focused_app and (focused_app in meta.name.lower() or focused_app in meta.description.lower()):
                score += 0.15
                
            # 3. Permission level suitability
            if meta.permission_level in ["LOW", "MEDIUM"]:
                score += 0.10
                
            # 4. Historical success rate boost
            hist_score = self.historical_success_map.get(meta.name, 0.95)
            score += hist_score * 0.10
            
            scored_candidates.append((tool, min(1.0, score)))
            
        scored_candidates.sort(key=lambda item: item[1], reverse=True)
        return scored_candidates
