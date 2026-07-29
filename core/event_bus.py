import asyncio
from typing import Dict, List, Callable, Awaitable, Optional
from core.interfaces import IEventBus
from core.models import EventModel
from core.event_store import EventStore
from observability.logger import logger

EventMiddleware = Callable[[EventModel], Awaitable[EventModel]]

class AsyncEventBus(IEventBus):
    """Async Event Bus supporting Middleware, Versioning, Auto-Persistence via EventStore, and Session Event Replay."""
    
    def __init__(self, db_path: str = "data/event_store.db", event_store: Optional[EventStore] = None):
        self.event_store = event_store or EventStore(db_path=db_path)
        self._subscribers: Dict[str, List[Callable[[EventModel], Awaitable[None]]]] = {}
        self._middlewares: List[EventMiddleware] = []
        self._in_memory_history: List[EventModel] = []

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

        # 2. In-Memory History
        self._in_memory_history.append(current_event)
        
        # 3. Persistent SQLite Storage via EventStore
        self.event_store.save_event(current_event)
            
        # 4. Dispatch to Subscribers
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
        return self.event_store.query_events(correlation_id=correlation_id, limit=limit)

    async def replay_events(self, correlation_id: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        """Replays historical events for a specific correlation ID through a target handler."""
        events = self.get_event_history(correlation_id=correlation_id)
        for ev in events:
            await handler(ev)
