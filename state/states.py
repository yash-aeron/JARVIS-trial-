from enum import Enum, auto
from typing import Dict, List

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

# Explicit Allowed Transitions Matrix
ALLOWED_TRANSITIONS: Dict[AssistantState, List[AssistantState]] = {
    AssistantState.IDLE: [
        AssistantState.WAKE_WORD_DETECTED, 
        AssistantState.LISTENING, 
        AssistantState.THINKING, 
        AssistantState.PLANNING,
        AssistantState.EXECUTING,
        AssistantState.SPEAKING,
        AssistantState.ERROR
    ],
    AssistantState.WAKE_WORD_DETECTED: [
        AssistantState.LISTENING, 
        AssistantState.IDLE, 
        AssistantState.ERROR
    ],
    AssistantState.LISTENING: [
        AssistantState.THINKING, 
        AssistantState.IDLE, 
        AssistantState.ERROR
    ],
    AssistantState.THINKING: [
        AssistantState.PLANNING,
        AssistantState.EXECUTING,
        AssistantState.SPEAKING,
        AssistantState.LISTENING,
        AssistantState.IDLE,
        AssistantState.ERROR
    ],
    AssistantState.PLANNING: [
        AssistantState.EXECUTING, 
        AssistantState.IDLE, 
        AssistantState.ERROR
    ],
    AssistantState.EXECUTING: [
        AssistantState.SPEAKING, 
        AssistantState.IDLE, 
        AssistantState.ERROR
    ],
    AssistantState.SPEAKING: [
        AssistantState.IDLE, 
        AssistantState.LISTENING, 
        AssistantState.ERROR
    ],
    AssistantState.ERROR: [
        AssistantState.IDLE,
        AssistantState.LISTENING
    ]
}
