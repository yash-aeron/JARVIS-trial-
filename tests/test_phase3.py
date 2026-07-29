"""
tests/test_phase3.py — Unit and integration tests for Phase 3 Memory upgrades.
"""
import pytest
import os
import uuid
import time

from memory.schema import MemoryItemModel, EpisodicMemoryItemModel, ProceduralMemoryItemModel
from memory.memory_manager import MemoryManager


def test_episodic_memory_store_and_query():
    """Test storing and querying session-scoped episodic events."""
    db_path = "data/test_episodic_memory.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    mem_mgr = MemoryManager(db_path=db_path)
    session_id = f"session_{uuid.uuid4()}"

    ep1 = EpisodicMemoryItemModel(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        event_type="user_command",
        summary="User asked to open Notepad"
    )
    ep2 = EpisodicMemoryItemModel(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        event_type="tool_execution",
        summary="ApplicationLauncherTool executed notepad.exe"
    )

    mem_mgr.store_episodic(ep1)
    mem_mgr.store_episodic(ep2)

    episodes = mem_mgr.get_session_episodes(session_id)
    assert len(episodes) == 2
    assert episodes[0].summary == "User asked to open Notepad"
    assert episodes[1].summary == "ApplicationLauncherTool executed notepad.exe"


def test_procedural_memory_store_and_recall():
    """Test storing and recalling successful plan execution sequences for recurring goals."""
    db_path = "data/test_procedural_memory.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    mem_mgr = MemoryManager(db_path=db_path)
    goal = "Open Chrome and check system status"

    proc = ProceduralMemoryItemModel(
        user_goal=goal,
        capabilities_used=["open_application", "system_control"],
        successful_plan_json='{"steps": [{"capability": "open_application"}, {"capability": "system_control"}]}',
        execution_count=3,
        success_rate=1.0
    )
    mem_mgr.store_procedural(proc)

    recalled = mem_mgr.recall_procedural(goal)
    assert recalled is not None
    assert recalled.user_goal == goal
    assert "open_application" in recalled.capabilities_used
    assert recalled.execution_count == 3


def test_rolling_session_summarization():
    """Test compressing raw session episodic history into a long-term semantic memory item."""
    db_path = "data/test_rolling_summarization.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    mem_mgr = MemoryManager(db_path=db_path)
    session_id = "session_dev_build_1"

    ep1 = EpisodicMemoryItemModel(
        session_id=session_id,
        correlation_id="cid_1",
        event_type="user_command",
        summary="Built JARVIS AI OS project"
    )
    ep2 = EpisodicMemoryItemModel(
        session_id=session_id,
        correlation_id="cid_2",
        event_type="tool_execution",
        summary="Executed 24 unit and integration tests successfully"
    )

    mem_mgr.store_episodic(ep1)
    mem_mgr.store_episodic(ep2)

    item_id = mem_mgr.summarize_session_to_semantic(session_id)
    assert item_id is not None

    summaries = mem_mgr.query(tag="session_summary")
    assert len(summaries) >= 1
    assert session_id in summaries[0].content
    assert "24 unit and integration tests" in summaries[0].content
