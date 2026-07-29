import heapq
import time
from typing import Dict, List, Optional
from core.models import ActionItemModel
from observability.logger import logger

class PriorityActionItem:
    """Wrapper for heapq priority sorting by priority rating descending."""
    
    def __init__(self, item: ActionItemModel):
        self.item = item

    def __lt__(self, other: 'PriorityActionItem') -> bool:
        # Higher priority value executes first
        return self.item.priority > other.item.priority

class ActionQueue:
    """Production Action Queue supporting Priority Ordering, Cancellation, Pause/Resume, ETA, and Progress tracking."""
    
    def __init__(self):
        self._heap: List[PriorityActionItem] = []
        self._items_map: Dict[str, ActionItemModel] = {}
        self._is_paused = False

    def enqueue(self, item: ActionItemModel) -> None:
        self._items_map[item.item_id] = item
        heapq.heappush(self._heap, PriorityActionItem(item))
        logger.info(f"[ActionQueue] Enqueued item '{item.item_id}' [Capability: {item.capability}, Priority: {item.priority}]")

    def dequeue(self) -> Optional[ActionItemModel]:
        if self._is_paused or not self._heap:
            return None
        p_item = heapq.heappop(self._heap)
        return p_item.item

    def cancel(self, item_id: str) -> bool:
        item = self._items_map.get(item_id)
        if item and item.state in ["PENDING", "RUNNING", "PAUSED"]:
            item.state = "CANCELLED"
            logger.info(f"[ActionQueue] Cancelled item '{item_id}'")
            return True
        return False

    def pause(self) -> None:
        self._is_paused = True
        logger.info("[ActionQueue] Queue execution paused.")

    def resume(self) -> None:
        self._is_paused = False
        logger.info("[ActionQueue] Queue execution resumed.")

    def update_progress(self, item_id: str, progress_percent: float, eta_sec: Optional[float] = None) -> None:
        item = self._items_map.get(item_id)
        if item:
            item.progress_percent = progress_percent
            item.eta_sec = eta_sec

    def list_all(self) -> List[ActionItemModel]:
        return list(self._items_map.values())
