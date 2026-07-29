from typing import List, Callable, Dict, Optional
from pydantic import BaseModel, Field
from observability.logger import logger

class ModeProfileModel(BaseModel):
    name: str
    voice_feedback: bool = True
    notification_level: str = "normal"  # silent | minimal | normal | verbose
    allowed_capabilities: List[str] = Field(default_factory=list)
    auto_launch_apps: List[str] = Field(default_factory=list)
    resource_priority: str = "balanced" # low | balanced | high

_MODE_PROFILES: Dict[str, ModeProfileModel] = {
    "Study": ModeProfileModel(
        name="Study", voice_feedback=True, notification_level="minimal",
        allowed_capabilities=["read_context", "recall_memory", "get_weather"],
        auto_launch_apps=["notepad"], resource_priority="balanced"
    ),
    "Coding": ModeProfileModel(
        name="Coding", voice_feedback=False, notification_level="minimal",
        allowed_capabilities=["open_application", "app_automation", "read_context", "query_project_memory"],
        auto_launch_apps=["vscode"], resource_priority="high"
    ),
    "Developer": ModeProfileModel(
        name="Developer", voice_feedback=False, notification_level="verbose",
        allowed_capabilities=["open_application", "app_automation", "read_context", "system_control", "query_project_memory"],
        auto_launch_apps=["vscode", "terminal"], resource_priority="high"
    ),
    "Gaming": ModeProfileModel(
        name="Gaming", voice_feedback=False, notification_level="silent",
        allowed_capabilities=["system_control"],
        auto_launch_apps=[], resource_priority="high"
    ),
    "Focus": ModeProfileModel(
        name="Focus", voice_feedback=False, notification_level="silent",
        allowed_capabilities=["read_context"],
        auto_launch_apps=[], resource_priority="low"
    ),
    "Meeting": ModeProfileModel(
        name="Meeting", voice_feedback=False, notification_level="minimal",
        allowed_capabilities=["read_context", "get_clipboard"],
        auto_launch_apps=["teams"], resource_priority="balanced"
    ),
    "Presentation": ModeProfileModel(
        name="Presentation", voice_feedback=True, notification_level="silent",
        allowed_capabilities=["open_application"],
        auto_launch_apps=["powerpoint"], resource_priority="balanced"
    ),
    "Travel": ModeProfileModel(
        name="Travel", voice_feedback=True, notification_level="normal",
        allowed_capabilities=["get_weather", "read_context"],
        auto_launch_apps=[], resource_priority="low"
    ),
}

class ModeManager:
    """Manages operating modes and profiles (Study, Coding, Developer, Gaming, Focus, Meeting, Presentation, Travel)."""

    MODES = list(_MODE_PROFILES.keys())

    def __init__(self, initial_mode: str = "Developer"):
        self._current_mode = initial_mode if initial_mode in _MODE_PROFILES else "Developer"
        self._listeners: List[Callable[[ModeProfileModel], None]] = []

    @property
    def current_mode(self) -> str:
        return self._current_mode

    @property
    def active_profile(self) -> ModeProfileModel:
        return _MODE_PROFILES[self._current_mode]

    def set_mode(self, new_mode: str) -> bool:
        if new_mode in _MODE_PROFILES:
            old_mode = self._current_mode
            self._current_mode = new_mode
            profile = self.active_profile
            logger.info(f"[ModeManager] Switched mode from '{old_mode}' to '{new_mode}' (Notification: {profile.notification_level})")
            for listener in self._listeners:
                try:
                    listener(profile)
                except Exception as exc:
                    logger.warning(f"[ModeManager] Listener error on mode change: {exc}")
            return True
        return False

    def add_listener(self, listener: Callable[[ModeProfileModel], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)
