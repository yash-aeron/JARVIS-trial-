from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class RuntimeContextSnapshot:
    focused_app: str = "VS Code"
    active_project: str = "JARVIS"
    clipboard_content: str = ""
    browser_tab: str = "Python Documentation"
    active_mode: str = "Developer"

class ContextManager:
    """Manages real-time transient runtime context snapshot (Focused app, Clipboard, Active project)."""
    
    def __init__(self):
        self._snapshot = RuntimeContextSnapshot()

    def get_snapshot(self) -> RuntimeContextSnapshot:
        return self._snapshot

    def update(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self._snapshot, k):
                setattr(self._snapshot, k, v)
