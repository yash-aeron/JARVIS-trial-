from typing import List, Callable
from observability.logger import logger

class ModeManager:
    """Manages operating modes (Study, Coding, Developer, Gaming, Focus, Meeting, Presentation, Travel)."""
    
    MODES = ["Study", "Coding", "Developer", "Gaming", "Focus", "Meeting", "Presentation", "Travel"]

    def __init__(self, initial_mode: str = "Developer"):
        self._current_mode = initial_mode if initial_mode in self.MODES else "Developer"
        self._listeners: List[Callable[[str], None]] = []

    @property
    def current_mode(self) -> str:
        return self._current_mode

    def set_mode(self, new_mode: str) -> bool:
        if new_mode in self.MODES:
            old_mode = self._current_mode
            self._current_mode = new_mode
            logger.info(f"[ModeManager] Switched mode from '{old_mode}' to '{new_mode}'")
            for listener in self._listeners:
                try:
                    listener(new_mode)
                except Exception:
                    pass
            return True
        return False

    def add_listener(self, listener: Callable[[str], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)
