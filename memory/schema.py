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

class EpisodicMemoryItemModel(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    correlation_id: str
    event_type: str  # user_command | tool_execution | system_event | error
    summary: str
    details: str = ""
    timestamp: float = Field(default_factory=lambda: time.time())

class ProceduralMemoryItemModel(BaseModel):
    procedure_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_goal: str
    capabilities_used: List[str] = Field(default_factory=list)
    successful_plan_json: str
    execution_count: int = 1
    success_rate: float = 1.0
    avg_latency_sec: float = 0.0
    last_executed: float = Field(default_factory=lambda: time.time())
