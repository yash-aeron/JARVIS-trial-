import pytest
import asyncio
import uuid
from core.app import JARVISApp
from state.states import AssistantState
from memory.schema import MemoryItemModel
from memory.memory_manager import MemoryManager

@pytest.mark.asyncio
async def test_scenario_open_chrome_and_vscode():
    """Scenario Test: Verifies pipeline execution for opening developer desktop tools."""
    app = JARVISApp()
    await app.initialize()
    
    cid = str(uuid.uuid4())
    res = await app.process_user_command("Open Chrome and VS Code", correlation_id=cid)
    
    assert res["correlation_id"] == cid
    assert len(res["execution_results"]) >= 1
    assert res["execution_results"][0]["status"] == "completed"
    
    await app.shutdown()

@pytest.mark.asyncio
async def test_scenario_multilingual_code_switching():
    """Scenario Test: Verifies pipeline handling of Hinglish code-switching requests."""
    app = JARVISApp()
    await app.initialize()
    
    cid = str(uuid.uuid4())
    res = await app.process_user_command("Jarvis, Chrome kholo and check system status", correlation_id=cid)
    
    assert res["correlation_id"] == cid
    assert res["execution_results"][0]["status"] == "completed"
    
    await app.shutdown()

@pytest.mark.asyncio
async def test_scenario_memory_store_and_recall():
    """Scenario Test: Verifies storing and recalling user memory items with ranking."""
    mem_mgr = MemoryManager(db_path="data/test_scenario_memory.db")
    item = MemoryItemModel(
        content="User project preference is Python 3.11 with PySide6",
        tags=["preference", "python", "gui"],
        importance=4.5,
        project="JARVIS",
        language="en-US"
    )
    mem_mgr.store(item)
    
    ranked = mem_mgr.query_and_rank(query_tags=["python"])
    assert len(ranked) >= 1
    top_item, score = ranked[0]
    assert "Python 3.11" in top_item.content
    assert score > 3.0
