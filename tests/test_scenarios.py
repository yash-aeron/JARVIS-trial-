import pytest
import asyncio
import uuid
from core.app import JARVISApp
from state.states import AssistantState

@pytest.mark.asyncio
async def test_scenario_open_application_workflow():
    """Scenario Test: Verifies complete input-to-speech execution pipeline for opening an application."""
    app = JARVISApp()
    await app.initialize()
    
    cid = str(uuid.uuid4())
    res = await app.process_user_command("Open notepad", correlation_id=cid)
    
    # 1. Pipeline Response Assertions
    assert res["correlation_id"] == cid
    assert res["intent"] in ["SINGLE_TOOL", "MULTI_STEP_PLAN"]
    assert len(res["execution_results"]) >= 1
    assert res["execution_results"][0]["status"] == "completed"
    
    # 2. Event Store Persistence Check
    history = app.event_bus.get_event_history(correlation_id=cid)
    topics = [ev.topic for ev in history]
    assert "intent.detected" in topics
    assert "plan.created" in topics
    assert "tool.started" in topics
    assert "tool.finished" in topics
    assert "speech.spoke" in topics
    
    # 3. Final State Check
    assert app.state_manager.current_state == AssistantState.IDLE
    
    await app.shutdown()

@pytest.mark.asyncio
async def test_scenario_system_status_check():
    """Scenario Test: Verifies system hardware query pipeline execution."""
    app = JARVISApp()
    await app.initialize()
    
    cid = str(uuid.uuid4())
    res = await app.process_user_command("Check system status", correlation_id=cid)
    
    assert res["correlation_id"] == cid
    assert res["execution_results"][0]["status"] == "completed"
    
    await app.shutdown()
