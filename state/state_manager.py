import asyncio
import uuid
from typing import Callable, List, Optional
from state.states import AssistantState
from core.interfaces import IEventBus, EventModel

class StateManager:
    """Centralized Assistant State Machine manager publishing EventModel with correlation ID."""
    
    def __init__(self, event_bus: Optional[IEventBus] = None):
        self._current_state: AssistantState = AssistantState.IDLE
        self._event_bus = event_bus
        self._subscribers: List[Callable[[AssistantState, AssistantState], None]] = []

    @property
    def current_state(self) -> AssistantState:
        return self._current_state

    def set_state(self, new_state: AssistantState, reason: str = "", correlation_id: Optional[str] = None) -> None:
        old_state = self._current_state
        if old_state == new_state:
            return
            
        self._current_state = new_state
        
        for subscriber in self._subscribers:
            try:
                subscriber(old_state, new_state)
            except Exception:
                pass
                
        if self._event_bus:
            asyncio.create_task(
                self._event_bus.publish(
                    EventModel(
                        correlation_id=correlation_id or str(uuid.uuid4()),
                        topic="system.state_changed",
                        data={"old_state": old_state.name, "new_state": new_state.name, "reason": reason},
                        sender="StateManager"
                    )
                )
            )

    def subscribe(self, handler: Callable[[AssistantState, AssistantState], None]) -> None:
        if handler not in self._subscribers:
            self._subscribers.append(handler)
