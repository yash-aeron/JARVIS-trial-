import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

@dataclass
class MemoryItem:
    content: str
    tags: List[str] = field(default_factory=list)
    importance: float = 1.0  # 0.0 to 5.0
    project: str = "general"
    language: str = "en-US"
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"
