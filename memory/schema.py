import uuid
import time
from pydantic import BaseModel, Field
from typing import List, Optional

class MemoryItemModel(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    tags: List[str] = Field(default_factory=list)
    importance: float = 1.0  # 0.0 to 5.0 rating
    project: str = "general"
    language: str = "en-US"
    source: str = "conversation"  # conversation, document, user_input, web
    confidence: float = 0.95
    access_count: int = 0
    last_accessed: float = Field(default_factory=lambda: time.time())
    timestamp: float = Field(default_factory=lambda: time.time())
    embedding_version: str = "v1.0"
