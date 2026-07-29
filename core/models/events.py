import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from core.models.system import LanguageDetectionModel

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
    language_details: LanguageDetectionModel = Field(default_factory=LanguageDetectionModel)

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

class GenericEventData(BaseModel):
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)

class EventModel(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    sender: str
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    payload: BaseModel = Field(default_factory=GenericEventData)

    @property
    def data(self) -> Dict[str, Any]:
        return self.payload.model_dump()
