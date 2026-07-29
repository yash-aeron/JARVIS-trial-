from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class LanguageDetectionModel(BaseModel):
    language: str = "en-US"
    confidence: float = 1.0
    is_code_switching: bool = False

class SystemStatusModel(BaseModel):
    cpu_percent: float
    ram_percent: float
    disk_percent: float

class BenchmarkResultModel(BaseModel):
    startup_time_ms: float = 0.0
    planner_latency_ms: float = 0.0
    executor_latency_ms: float = 0.0
    event_bus_latency_ms: float = 0.0
    memory_retrieval_latency_ms: float = 0.0
    tool_execution_latency_ms: float = 0.0

class ToolSelectionEvalModel(BaseModel):
    predicted_tool: str
    expected_tool: str
    match: bool

class PlanOptimalityEvalModel(BaseModel):
    steps: int
    max_expected: int
    optimal: bool

class VRAMStatusModel(BaseModel):
    vram_budget_mb: float
    allocated_mb: float
    free_mb: float
    is_vram_pressure: bool
    loaded_models: List[str] = Field(default_factory=list)

class MetricsSummaryModel(BaseModel):
    system_status: SystemStatusModel
    benchmarks: BenchmarkResultModel
    counters: Dict[str, int] = Field(default_factory=dict)
