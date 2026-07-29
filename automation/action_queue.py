from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ActionQueueState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"

class ActionItemModel(BaseModel):
    item_id: str
    correlation_id: str
    capability: str
    args: Dict[str, Any] = Field(default_factory=dict)
    state: ActionQueueState = ActionQueueState.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ActionQueue:
    """Async Queue managing PENDING, RUNNING, PAUSED, FAILED, COMPLETED action states."""
    
    def __init__(self):
        self._queue: List[ActionItemModel] = []

    def enqueue(self, item: ActionItemModel) -> None:
        self._queue.append(item)

    def get_pending(self) -> List[ActionItemModel]:
        return [item for item in self._queue if item.state == ActionQueueState.PENDING]

    def get_all(self) -> List[ActionItemModel]:
        return self._queue
