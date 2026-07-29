import asyncio
import uuid
from typing import Dict, List, Callable, Awaitable
from core.interfaces import IEventBus, EventModel

class AsyncEventBus(IEventBus):
    """Async Event & Message Bus with Event Store tracking and Correlation IDs."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[EventModel], Awaitable[None]]]] = {}
        self._event_store: List[EventModel] = []

    async def publish(self, event: EventModel) -> None:
        self._event_store.append(event)
        
        handlers_to_call = []
        for topic, handlers in self._subscribers.items():
            if topic == "*" or topic == event.topic or (topic.endswith(".*") and event.topic.startswith(topic[:-2])):
                handlers_to_call.extend(handlers)
                
        if handlers_to_call:
            await asyncio.gather(*(h(event) for h in handlers_to_call), return_exceptions=True)

    def subscribe(self, topic: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        if topic in self._subscribers and handler in self._subscribers[topic]:
            self._subscribers[topic].remove(handler)

    def get_event_history(self, correlation_id: str = None, limit: int = 100) -> List[EventModel]:
        if correlation_id:
            return [ev for ev in self._event_store if ev.correlation_id == correlation_id][-limit:]
        return self._event_store[-limit:]
