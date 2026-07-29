"""
tests/test_phase6.py — Unit and integration test suite for Phase 6 Multi-Agent Architecture.
"""
import pytest
import asyncio

from core.app import bootstrap_container
from core.event_bus import AsyncEventBus
from agent.subagents import (
    SubagentTaskRequestModel, SubagentTaskResultModel,
    PlanningSubagent, MemorySubagent, ExecutionSubagent
)
from agent.executive import ExecutiveAgent
from memory.memory_manager import MemoryManager
from brain.planner import Planner
from automation.executor import PlanExecutor


@pytest.mark.asyncio
async def test_subagent_task_request_response_models():
    """Validate Pydantic models for subagent task requests and results."""
    req = SubagentTaskRequestModel(
        task_id="task_100",
        correlation_id="cid_100",
        target_subagent="planning",
        prompt="Open VS Code"
    )
    res = SubagentTaskResultModel(
        task_id=req.task_id,
        correlation_id=req.correlation_id,
        subagent="planning",
        status="completed",
        output={"plan_id": "plan_123"}
    )

    assert req.target_subagent == "planning"
    assert res.status == "completed"
    assert res.output["plan_id"] == "plan_123"


@pytest.mark.asyncio
async def test_memory_subagent_event_publishing():
    """Verify MemorySubagent handles memory task and publishes completion event to AsyncEventBus."""
    bus = AsyncEventBus()
    db_path = "data/test_memory_subagent.db"
    mem_mgr = MemoryManager(db_path=db_path)
    mem_subagent = MemorySubagent(memory_manager=mem_mgr, event_bus=bus)

    received_events = []
    async def _listener(event):
        received_events.append(event)

    bus.subscribe("subagent.memory.completed", _listener)

    req = SubagentTaskRequestModel(
        task_id="task_mem_1",
        correlation_id="cid_mem_1",
        target_subagent="memory",
        prompt="Open Chrome"
    )
    res = await mem_subagent.handle_memory_task(req)

    assert res.status == "completed"
    assert len(received_events) == 1
    assert received_events[0].topic == "subagent.memory.completed"
    assert received_events[0].sender == "memory"


@pytest.mark.asyncio
async def test_executive_agent_subagent_wiring():
    """Verify ExecutiveAgent DI container resolution wires dedicated subagents cleanly."""
    container = bootstrap_container()
    exec_agent: ExecutiveAgent = container.resolve(ExecutiveAgent)

    assert exec_agent.planning_subagent is not None
    assert exec_agent.memory_subagent is not None
    assert exec_agent.execution_subagent is not None
    assert exec_agent.planning_subagent.name == "planning"
    assert exec_agent.memory_subagent.name == "memory"
    assert exec_agent.execution_subagent.name == "execution"
