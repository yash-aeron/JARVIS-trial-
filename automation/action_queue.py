import asyncio
from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable
from observability.logger import logger

class ActionQueueState(Enum):
    PENDING = auto()
    RUNNING = auto()
    PAUSED = auto()
    FAILED = auto()
    COMPLETED = auto()

@dataclass
class ActionItem:
    item_id: str
    tool_name: str
    args: Dict[str, Any]
    state: ActionQueueState = ActionQueueState.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ActionQueue:
    """Async Queue managing PENDING, RUNNING, PAUSED, FAILED, COMPLETED action states."""
    
    def __init__(self):
        self._queue: List[ActionItem] = []

    def enqueue(self, item: ActionItem) -> None:
        self._queue.append(item)
        logger.info(f"[ActionQueue] Enqueued action '{item.item_id}' ({item.tool_name})")

    def get_pending(self) -> List[ActionItem]:
        return [item for item in self._queue if item.state == ActionQueueState.PENDING]

    def get_all(self) -> List[ActionItem]:
        return self._queue
