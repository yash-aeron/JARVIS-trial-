# JARVIS Core Interfaces & Pydantic Data Models Specification

## Pydantic Core Models

Every data structure in JARVIS extends `pydantic.BaseModel` for validation, schema enforcement, and type safety.

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class EventModel(BaseModel):
    event_id: str
    correlation_id: str
    topic: str
    sender: str
    timestamp: float
    data: Dict[str, Any]

class PlanStepModel(BaseModel):
    step_id: int
    tool_name: str
    args: Dict[str, Any]
    expected_observation: str
    status: str = "PENDING"

class ExecutionPlanModel(BaseModel):
    plan_id: str
    correlation_id: str
    user_goal: str
    steps: List[PlanStepModel]
    version: str = "1.0.0"
```

## Core Interfaces Summary

- `IEventBus`: Async topic publish/subscribe with Event Store.
- `IService`: Subsystem lifecycle management (`start`, `stop`, `health_check`).
- `ILLMProvider`: Local/Remote LLM generation.
- `ISTTProvider`: Speech-to-Text transcription.
- `ITTSProvider`: Text-to-Speech synthesis.
- `ITool`: Tool metadata, `execute`, and `undo`.
- `ISkill`: Composite tool workflow execution.
- `IPlugin`: Dynamic plugin lifecycle hooks (`on_load`, `on_unload`).
