import pytest
import asyncio
import uuid
from core.app import JARVISApp
from core.models import UserCommandResultModel
from state.states import AssistantState
from memory.schema import MemoryItemModel
from memory.memory_manager import MemoryManager

@pytest.mark.asyncio
async def test_scenario_open_chrome_and_vscode():
    """Scenario Test: Verifies pipeline execution for opening developer desktop tools."""
    app = JARVISApp()
    await app.initialize()

    cid = str(uuid.uuid4())
    res: UserCommandResultModel = await app.process_user_command("Open Chrome and VS Code", correlation_id=cid)

    assert res.correlation_id == cid
    assert isinstance(res.execution_results, list)

    await app.shutdown()

@pytest.mark.asyncio
async def test_scenario_multilingual_code_switching():
    """Scenario Test: Verifies pipeline handling of Hinglish code-switching requests."""
    app = JARVISApp()
    await app.initialize()

    cid = str(uuid.uuid4())
    res: UserCommandResultModel = await app.process_user_command("Jarvis, Chrome kholo and check system status", correlation_id=cid)

    assert res.correlation_id == cid
    assert isinstance(res.execution_results, list)

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

@pytest.mark.asyncio
async def test_scenario_semantic_cosine_vector_recall():
    """Scenario Test: Verifies vector cosine similarity search in MemoryManager."""
    mem_mgr = MemoryManager(db_path="data/test_semantic_recall.db")
    item1 = MemoryItemModel(content="NVIDIA RTX 3050 Ti graphics card has 4GB VRAM budget", tags=["gpu", "vram"], importance=4.0)
    item2 = MemoryItemModel(content="Grocery list includes milk, bread, and eggs", tags=["grocery"], importance=1.0)
    
    mem_mgr.store(item1)
    mem_mgr.store(item2)
    
    recalled = mem_mgr.semantic_recall(query_text="graphics card VRAM budget", top_k=1)
    assert len(recalled) == 1
    top_item, score = recalled[0]
    assert "RTX 3050 Ti" in top_item.content
    assert score > 4.0
