import asyncio
import uuid
from typing import Dict, List, Callable, Awaitable, Any
from core.interfaces import IEventBus, Event

class AsyncEventBus(IEventBus):
    """Async Event & Message Bus with Event Store tracking (Event Sourcing)."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Event], Awaitable[None]]]] = {}
        self._event_store: List[Event] = []

    async def publish(self, event: Event) -> None:
        if not event.event_id:
            event.event_id = str(uuid.uuid4())
            
        self._event_store.append(event)
        
        # Wildcard matching support (e.g. "speech.*", "*")
        handlers_to_call = []
        for topic, handlers in self._subscribers.items():
            if topic == "*" or topic == event.topic or (topic.endswith(".*") and event.topic.startswith(topic[:-2])):
                handlers_to_call.extend(handlers)
                
        if handlers_to_call:
            await asyncio.gather(*(h(event) for h in handlers_to_call), return_exceptions=True)

    def subscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None:
        if topic in self._subscribers and handler in self._subscribers[topic]:
            self._subscribers[topic].remove(handler)

    def get_event_history(self, limit: int = 100) -> List[Event]:
        return self._event_store[-limit:]
