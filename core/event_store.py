"""
core/event_store.py — Dedicated Event Store with Point-in-Time Snapshots, Audit Log Filtering, and Time-Travel Debugging support.
"""
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from core.models import EventModel
from observability.logger import logger


class StateSnapshotModel(BaseModel):
    """Point-in-Time state snapshot for event sourcing recovery."""
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state_name: str
    snapshot_data: Dict[str, Any] = Field(default_factory=dict)
    last_event_id: str
    timestamp: float = Field(default_factory=lambda: time.time())


class AuditLogRecordModel(BaseModel):
    """Audit log entry capturing sender, topic, correlation ID, and payload info."""
    event_id: str
    correlation_id: str
    topic: str
    sender: str
    timestamp: float
    summary: str


class EventStore:
    """Dedicated Event Store providing SQLite persistent event storage, state snapshots, audit logging, and replay querying."""

    def __init__(self, db_path: str = "data/event_store.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connect(self):
        """Yield a connection that is always closed — sqlite's context manager only commits."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_store (
                    event_id TEXT PRIMARY KEY,
                    correlation_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    data_json TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS state_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    state_name TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    last_event_id TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.commit()

    def save_event(self, event: EventModel) -> bool:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO event_store
                    (event_id, correlation_id, topic, sender, timestamp, data_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id, event.correlation_id,
                    event.topic, event.sender,
                    event.timestamp, event.model_dump_json()
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[EventStore] Failed to save event '{event.event_id}': {e}")
            return False

    def save_snapshot(self, snapshot: StateSnapshotModel) -> bool:
        """Point-in-Time state snapshot saving."""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO state_snapshots
                    (snapshot_id, state_name, snapshot_json, last_event_id, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    snapshot.snapshot_id, snapshot.state_name,
                    snapshot.model_dump_json(), snapshot.last_event_id,
                    snapshot.timestamp
                ))
                conn.commit()
                logger.info(f"[EventStore] Saved point-in-time snapshot '{snapshot.snapshot_id}' [State: {snapshot.state_name}]")
                return True
        except Exception as e:
            logger.error(f"[EventStore] Failed to save snapshot '{snapshot.snapshot_id}': {e}")
            return False

    def get_latest_snapshot(self, state_name: str) -> Optional[StateSnapshotModel]:
        """Fetch latest point-in-time snapshot for a given state component."""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                # rowid breaks ties: time.time() has coarse resolution on Windows.
                row = cursor.execute("""
                    SELECT snapshot_json FROM state_snapshots
                    WHERE state_name = ? ORDER BY timestamp DESC, rowid DESC LIMIT 1
                """, (state_name,)).fetchone()
                if row:
                    return StateSnapshotModel.model_validate_json(row[0])
        except Exception as e:
            logger.error(f"[EventStore] Failed to fetch latest snapshot for '{state_name}': {e}")
        return None

    def query_audit_logs(
        self,
        sender: Optional[str] = None,
        topic: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLogRecordModel]:
        """Audit Log View: filter who/what triggered each event."""
        query = "SELECT event_id, correlation_id, topic, sender, timestamp, data_json FROM event_store WHERE 1=1"
        params: List[Any] = []

        if sender:
            query += " AND sender = ?"
            params.append(sender)
        if topic:
            query += " AND topic = ?"
            params.append(topic)
        if correlation_id:
            query += " AND correlation_id = ?"
            params.append(correlation_id)

        # Select the NEWEST rows, then present them oldest-first.
        query += " ORDER BY timestamp DESC, rowid DESC LIMIT ?"
        params.append(limit)

        records: List[AuditLogRecordModel] = []
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                rows = cursor.execute(query, params).fetchall()
                for r in reversed(rows):
                    ev_model = EventModel.model_validate_json(r[5])
                    summary = f"Event '{ev_model.topic}' sent by '{ev_model.sender}' [CID: {ev_model.correlation_id}]"
                    records.append(AuditLogRecordModel(
                        event_id=r[0], correlation_id=r[1],
                        topic=r[2], sender=r[3], timestamp=r[4],
                        summary=summary
                    ))
        except Exception as e:
            logger.error(f"[EventStore] Failed to query audit logs: {e}")
        return records

    def query_events(self, correlation_id: Optional[str] = None, limit: int = 100) -> List[EventModel]:
        query = "SELECT data_json FROM event_store"
        params: List[Any] = []
        if correlation_id:
            query += " WHERE correlation_id = ?"
            params.append(correlation_id)
        # Newest `limit` rows, returned in chronological order so replay is correct.
        query += " ORDER BY timestamp DESC, rowid DESC LIMIT ?"
        params.append(limit)

        events: List[EventModel] = []
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                rows = cursor.execute(query, params).fetchall()
                for row in reversed(rows):
                    events.append(EventModel.model_validate_json(row[0]))
        except Exception as e:
            logger.error(f"[EventStore] Failed to query events: {e}")
        return events
