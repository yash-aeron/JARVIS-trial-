import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from core.models.tools import ToolResultModel

class ServiceState(str, Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"

class ExecutionContextModel(BaseModel):
    focused_app: str = "VS Code"
    foreground_process_name: str = "code.exe"
    foreground_pid: Optional[int] = None
    active_window_title: str = "JARVIS Workspace"
    clipboard_content: str = ""
    screen_resolution: str = "1920x1080"
    active_mode: str = "Developer"
    vision_observation: Optional[Dict[str, Any]] = None

class ActionItemModel(BaseModel):
    item_id: str
    correlation_id: str
    capability: str
    args: Dict[str, Any] = Field(default_factory=dict)
    state: str = "PENDING"  # PENDING, RUNNING, PAUSED, FAILED, COMPLETED
    priority: int = 1  # 1 = Normal, 5 = High, 10 = Critical
    progress_percent: float = 0.0
    eta_sec: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class UserCommandResultModel(BaseModel):
    correlation_id: str
    utterance: str
    intent: str
    execution_results: List[ToolResultModel] = Field(default_factory=list)
    response: str

class UndoRecordModel(BaseModel):
    request_id: str
    correlation_id: str
    tool_name: str
    timestamp: float = Field(default_factory=lambda: time.time())
