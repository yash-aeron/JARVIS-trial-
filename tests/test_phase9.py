"""
tests/test_phase9.py — Unit and integration tests for Phase 9 Event Store Upgrades & Time-Travel Debugging.
"""
import pytest
import os
import uuid

from core.event_store import EventStore, StateSnapshotModel, AuditLogRecordModel
from core.event_bus import AsyncEventBus
from core.models import EventModel, GenericEventData
from automation.undo_manager import UndoManager
from tools.system_tools import ApplicationLauncherTool
from core.models.tools import ToolRequestModel, ToolResultModel


def test_event_store_point_in_time_snapshots():
    """Verify point-in-time state snapshot persistence and retrieval."""
    db_path = "data/test_snapshots_store.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    store = EventStore(db_path=db_path)
    snapshot = StateSnapshotModel(
        state_name="StateManager",
        snapshot_data={"state": "EXECUTING", "active_mode": "Coding"},
        last_event_id="ev_step_5"
    )

    assert store.save_snapshot(snapshot) is True

    latest = store.get_latest_snapshot("StateManager")
    assert latest is not None
    assert latest.snapshot_id == snapshot.snapshot_id
    assert latest.last_event_id == "ev_step_5"
    assert latest.snapshot_data["active_mode"] == "Coding"


def test_event_store_audit_log_querying():
    """Verify audit log filtering by sender, topic, and correlation ID."""
    db_path = "data/test_audit_store.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    store = EventStore(db_path=db_path)
    cid = f"cid_audit_{uuid.uuid4()}"

    ev1 = EventModel(
        correlation_id=cid,
        topic="speech.recognized",
        sender="SpeechManager",
        payload=GenericEventData(data={"text": "Open Chrome"})
    )
    ev2 = EventModel(
        correlation_id=cid,
        topic="tool.started",
        sender="PlanExecutor",
        payload=GenericEventData(data={"tool": "app_launcher"})
    )

    store.save_event(ev1)
    store.save_event(ev2)

    audit_logs = store.query_audit_logs(correlation_id=cid)
    assert len(audit_logs) == 2
    senders = [a.sender for a in audit_logs]
    assert "SpeechManager" in senders
    assert "PlanExecutor" in senders

    sender_logs = store.query_audit_logs(sender="SpeechManager")
    assert len(sender_logs) == 1
    assert sender_logs[0].topic == "speech.recognized"


@pytest.mark.asyncio
async def test_time_travel_undo_chain_integration():
    """Verify tying UndoManager records to event_id for time-travel debugging."""
    undo_mgr = UndoManager()
    tool = ApplicationLauncherTool()

    cid = f"cid_undo_{uuid.uuid4()}"
    ev_id = f"ev_undo_{uuid.uuid4()}"

    req = ToolRequestModel(
        request_id="req_undo_1",
        correlation_id=cid,
        capability="open_application",
        tool_name="app_launcher",
        args={"app_name": "notepad", "action": "focus"}
    )
    res = ToolResultModel(request_id=req.request_id, correlation_id=cid, status="completed")

    undo_mgr.record(tool, req, res, event_id=ev_id)
    history = undo_mgr.get_history()

    assert len(history) == 1
    assert history[0].request_id == "req_undo_1"
    assert history[0].event_id == ev_id
    assert history[0].correlation_id == cid


@pytest.mark.asyncio
async def test_event_bus_snapshot_replay():
    """Verify point-in-time event replay starting after snapshot last_event_id."""
    db_path = "data/test_bus_snapshot_replay.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    bus = AsyncEventBus(db_path=db_path)
    cid = f"cid_replay_{uuid.uuid4()}"

    ev1 = EventModel(event_id="ev_1", correlation_id=cid, topic="test.t1", sender="s1", payload=GenericEventData())
    ev2 = EventModel(event_id="ev_2", correlation_id=cid, topic="test.t2", sender="s2", payload=GenericEventData())
    ev3 = EventModel(event_id="ev_3", correlation_id=cid, topic="test.t3", sender="s3", payload=GenericEventData())

    await bus.publish(ev1)
    await bus.publish(ev2)
    await bus.publish(ev3)

    # Save snapshot after ev_1
    snapshot = StateSnapshotModel(state_name="TestState", snapshot_data={}, last_event_id="ev_1")
    bus.event_store.save_snapshot(snapshot)

    replayed = []
    async def _replay_handler(ev):
        replayed.append(ev)

    snapshot_id = await bus.replay_from_snapshot("TestState", _replay_handler)
    assert snapshot_id == snapshot.snapshot_id
    assert len(replayed) == 2
    assert replayed[0].event_id == "ev_2"
    assert replayed[1].event_id == "ev_3"
