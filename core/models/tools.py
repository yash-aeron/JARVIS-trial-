import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class OpenApplicationArgs(BaseModel):
    app_name: str
    action: str = "launch"  # launch, focus, close
    reuse_existing: bool = True

class SystemControlArgs(BaseModel):
    action: str = "get_status"  # get_status, set_volume, set_brightness

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
