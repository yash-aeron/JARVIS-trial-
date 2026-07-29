import uuid
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field
from datetime import datetime

class ToolMetadata(BaseModel):
    name: str
    description: str
    capabilities: List[str]
    permission_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    args_schema: Dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"

class ToolRequestModel(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str
    capability: str
    tool_name: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)
    timeout_sec: float = 10.0
    max_retries: int = 2
    is_cancelled: bool = False

class ToolResultModel(BaseModel):
    request_id: str
    correlation_id: str
    status: str  # "completed", "failed", "undone", "cancelled"
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

class EventModel(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    sender: str
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    data: Dict[str, Any] = Field(default_factory=dict)

# Dedicated Pydantic Event Payloads
class ToolStartedEventData(BaseModel):
    step_id: int
    capability: str
    tool_name: str

class ToolFinishedEventData(BaseModel):
    step_id: int
    tool_name: str
    status: str
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

class SpeechRecognizedEventData(BaseModel):
    text: str
    language_details: Dict[str, Any] = Field(default_factory=dict)

class SpeechSpokeEventData(BaseModel):
    text: str
    voice: str
    audio_length: int

class StateChangedEventData(BaseModel):
    old_state: str
    new_state: str
    reason: str

class IntentDetectedEventData(BaseModel):
    utterance: str
    intent_category: str
    confidence: float
    risk_level: str

class PlanCreatedEventData(BaseModel):
    plan_id: str
    correlation_id: str
    total_steps: int
    user_goal: str
