import asyncio
import uuid
from typing import Callable, List, Optional, Set
from state.states import AssistantState, ALLOWED_TRANSITIONS, StateTransitionError
from core.interfaces import IEventBus
from core.models import EventModel, StateChangedEventData
from observability.logger import logger

class StateManager:
    """Guarded Assistant State Machine manager enforcing valid state transitions."""
    
    def __init__(self, event_bus: Optional[IEventBus] = None):
        self._current_state: AssistantState = AssistantState.IDLE
        self._event_bus = event_bus
        self._subscribers: List[Callable[[AssistantState, AssistantState], None]] = []
        # Strong refs so fire-and-forget publishes aren't garbage collected mid-flight.
        self._pending_publishes: Set[asyncio.Task] = set()

    @property
    def current_state(self) -> AssistantState:
        return self._current_state

    def transition_to(self, new_state: AssistantState, reason: str = "", correlation_id: Optional[str] = None) -> None:
        """Enforces transition matrix rules. Raises StateTransitionError if illegal transition is attempted."""
        old_state = self._current_state
        if old_state == new_state:
            return
            
        allowed_next = ALLOWED_TRANSITIONS.get(old_state, [])
        if new_state not in allowed_next:
            err_msg = f"Illegal state transition attempted: {old_state.name} -> {new_state.name} (Reason: {reason})"
            logger.error(err_msg)
            raise StateTransitionError(err_msg)
            
        self._current_state = new_state
        logger.info(f"State transition: {old_state.name} -> {new_state.name} [{reason}]")
        
        for subscriber in self._subscribers:
            try:
                subscriber(old_state, new_state)
            except Exception as e:
                logger.warning(f"Subscriber error during state transition: {e}")
                
        if self._event_bus:
            payload = StateChangedEventData(old_state=old_state.name, new_state=new_state.name, reason=reason)
            event = EventModel(
                correlation_id=correlation_id or str(uuid.uuid4()),
                topic="system.state_changed",
                payload=payload,
                sender="StateManager"
            )
            # transition_to is sync and is called from both async paths and plain
            # sync callers (CLI/GUI bootstrap), where there is no running loop.
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                task = loop.create_task(self._event_bus.publish(event))
                self._pending_publishes.add(task)
                task.add_done_callback(self._pending_publishes.discard)
            else:
                try:
                    asyncio.run(self._event_bus.publish(event))
                except Exception as e:
                    logger.warning(f"Could not publish state change event outside an event loop: {e}")

    def set_state(self, new_state: AssistantState, reason: str = "", correlation_id: Optional[str] = None) -> None:
        """Alias for transition_to to maintain backward compatibility."""
        self.transition_to(new_state, reason=reason, correlation_id=correlation_id)

    def subscribe(self, handler: Callable[[AssistantState, AssistantState], None]) -> None:
        if handler not in self._subscribers:
            self._subscribers.append(handler)
