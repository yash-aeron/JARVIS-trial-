from enum import Enum, auto

class AssistantState(Enum):
    IDLE = auto()
    WAKE_WORD_DETECTED = auto()
    LISTENING = auto()
    THINKING = auto()
    PLANNING = auto()
    EXECUTING = auto()
    SPEAKING = auto()
    ERROR = auto()

class StateTransitionError(Exception):
    pass
