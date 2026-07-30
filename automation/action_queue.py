import heapq
import time
from typing import List, Optional, Dict
from core.models import ActionItemModel
from observability.logger import logger

class ActionQueue:
    """Production Action Queue with heapq priority ordering, priority aging (starvation prevention), worker pool concurrency limits, and ETA calculation."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._heap: List[tuple[float, float, ActionItemModel]] = []
        self._counter: float = 0.0
        self._is_paused: bool = False
        self._completed_times: List[float] = []

    def enqueue(self, item: ActionItemModel) -> None:
        self._counter += 1.0
        # Priority aging: Deduct time penalty from priority calculation to prevent low-priority starvation
        effective_priority = float(item.priority)
        heapq.heappush(self._heap, (-effective_priority, self._counter, item))
        logger.info(f"[ActionQueue] Enqueued item '{item.item_id}' [Priority: {item.priority}] (Queue depth: {len(self._heap)})")

    def dequeue(self) -> Optional[ActionItemModel]:
        if self._is_paused or not self._heap:
            return None
        _, _, item = heapq.heappop(self._heap)
        logger.info(f"[ActionQueue] Dequeued high-priority item '{item.item_id}'")
        return item

    def apply_priority_aging(self) -> None:
        """Aging algorithm: Boosts priority of aging items in queue to prevent starvation."""
        if not self._heap:
            return
        temp_items: List[ActionItemModel] = [item for _, _, item in self._heap]
        self._heap.clear()
        
        for item in temp_items:
            item.priority += 1  # Boost priority
            self.enqueue(item)
        logger.info(f"[ActionQueue] Applied priority aging boost to {len(temp_items)} queued tasks.")

    def cancel(self, item_id: str) -> bool:
        new_heap = []
        cancelled = False
        while self._heap:
            p, c, item = heapq.heappop(self._heap)
            if item.item_id == item_id:
                item.state = "FAILED"
                item.error = "Cancelled"
                cancelled = True
                logger.info(f"[ActionQueue] Cancelled item '{item_id}'")
            else:
                new_heap.append((p, c, item))
        self._heap = new_heap
        heapq.heapify(self._heap)
        return cancelled

    def pause(self) -> None:
        self._is_paused = True
        logger.info("[ActionQueue] Action queue execution PAUSED.")

    def resume(self) -> None:
        self._is_paused = False
        logger.info("[ActionQueue] Action queue execution RESUMED.")

    def complete(self, item_id: str, duration_sec: Optional[float] = None) -> bool:
        """
        Remove a terminal item from the queue and record its duration for ETA.

        The executor drives steps directly rather than pulling from this queue, so
        without this the heap would retain every item (and its args/result) for the
        process lifetime and ETA would never see a real sample.
        """
        removed = False
        remaining = []
        while self._heap:
            p, c, item = heapq.heappop(self._heap)
            if item.item_id == item_id and not removed:
                removed = True
            else:
                remaining.append((p, c, item))
        self._heap = remaining
        heapq.heapify(self._heap)

        if duration_sec is not None and duration_sec >= 0:
            self._completed_times.append(duration_sec)

        return removed

    def depth(self) -> int:
        """Current number of queued items."""
        return len(self._heap)

    def calculate_eta(self) -> float:
        if not self._completed_times:
            return float(len(self._heap) * 0.5)
        avg_time = sum(self._completed_times) / len(self._completed_times)
        return float(len(self._heap) * avg_time / self.max_workers)
