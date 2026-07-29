import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from core.models.execution import ExecutionContextModel

class PlannerContextModel(BaseModel):
    user_goal: str
    capabilities_needed: List[str] = Field(default_factory=list)
    execution_context: ExecutionContextModel = Field(default_factory=ExecutionContextModel)

class PlanStepModel(BaseModel):
    step_id: int
    capability: str
    args: Dict[str, Any] = Field(default_factory=dict)
    expected_observation: str
    depends_on: List[int] = Field(default_factory=list)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED

class ExecutionPlanModel(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str
    user_goal: str
    steps: List[PlanStepModel] = Field(default_factory=list)
    version: str = "1.0.0"

class LLMExecutionPlanResponse(BaseModel):
    user_goal: str
    steps: List[PlanStepModel] = Field(default_factory=list)
