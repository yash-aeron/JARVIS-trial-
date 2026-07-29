import os
import sqlite3
from typing import List, Optional
from core.models import EventModel
from observability.logger import logger

class EventStore:
    """Dedicated Event Store providing SQLite persistent event storage and historical replay querying."""
    
    def __init__(self, db_path: str = "data/event_store.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or "data", exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
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
            conn.commit()

    def save_event(self, event: EventModel) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
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

    def query_events(self, correlation_id: Optional[str] = None, limit: int = 100) -> List[EventModel]:
        query = "SELECT data_json FROM event_store"
        params = []
        if correlation_id:
            query += " WHERE correlation_id = ?"
            params.append(correlation_id)
        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)

        events: List[EventModel] = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                rows = cursor.execute(query, params).fetchall()
                for row in rows:
                    events.append(EventModel.model_validate_json(row[0]))
        except Exception as e:
            logger.error(f"[EventStore] Failed to query events: {e}")
        return events
