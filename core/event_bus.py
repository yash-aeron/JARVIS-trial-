import os
import asyncio
import sqlite3
from typing import Dict, List, Callable, Awaitable, Optional, Any
from core.interfaces import IEventBus
from core.models import EventModel
from observability.logger import logger

EventMiddleware = Callable[[EventModel], Awaitable[EventModel]]

class AsyncEventBus(IEventBus):
    """Async Event Bus supporting Middleware, Versioning, Auto-Persistence, and Session Event Replay."""
    
    def __init__(self, db_path: str = "data/event_store.db"):
        self.db_path = db_path
        self._subscribers: Dict[str, List[Callable[[EventModel], Awaitable[None]]]] = {}
        self._middlewares: List[EventMiddleware] = []
        self._event_store: List[EventModel] = []
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

    def add_middleware(self, middleware: EventMiddleware) -> None:
        self._middlewares.append(middleware)

    async def publish(self, event: EventModel) -> None:
        # 1. Execute Middleware Chain
        current_event = event
        for mw in self._middlewares:
            try:
                current_event = await mw(current_event)
            except Exception as e:
                logger.error(f"[AsyncEventBus] Middleware error: {e}")

        # 2. In-Memory Store
        self._event_store.append(current_event)
        
        # 3. Persistent SQLite Event Store
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO event_store 
                    (event_id, correlation_id, topic, sender, timestamp, data_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    current_event.event_id, current_event.correlation_id, 
                    current_event.topic, current_event.sender, 
                    current_event.timestamp, current_event.model_dump_json()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"[AsyncEventBus] Failed to persist event {current_event.event_id}: {e}")
            
        # 4. Publish to Subscribers
        handlers_to_call = []
        for topic, handlers in self._subscribers.items():
            if topic == "*" or topic == current_event.topic or (topic.endswith(".*") and current_event.topic.startswith(topic[:-2])):
                handlers_to_call.extend(handlers)
                
        if handlers_to_call:
            await asyncio.gather(*(h(current_event) for h in handlers_to_call), return_exceptions=True)

    def subscribe(self, topic: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        if topic in self._subscribers and handler in self._subscribers[topic]:
            self._subscribers[topic].remove(handler)

    def get_event_history(self, correlation_id: Optional[str] = None, limit: int = 100) -> List[EventModel]:
        if correlation_id:
            return [ev for ev in self._event_store if ev.correlation_id == correlation_id][-limit:]
        return self._event_store[-limit:]

    async def replay_events(self, correlation_id: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        """Replays historical events for a specific correlation ID through a target handler."""
        events = self.get_event_history(correlation_id=correlation_id)
        for ev in events:
            await handler(ev)
