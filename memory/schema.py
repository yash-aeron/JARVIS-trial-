import uuid
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class MemoryItemModel(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    tags: List[str] = Field(default_factory=list)
    importance: float = 1.0  # 0.0 to 5.0
    project: str = "general"
    language: str = "en-US"
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    version: str = "1.0.0"
