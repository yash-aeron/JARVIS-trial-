from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class ContextSnapshotModel(BaseModel):
    focused_app: str = "VS Code"
    active_project: str = "JARVIS"
    clipboard_content: str = ""
    browser_tab: str = "Python Documentation"
    active_mode: str = "Developer"

class ContextManager:
    """Manages real-time transient runtime context snapshot (Focused app, Clipboard, Active project)."""
    
    def __init__(self):
        self._snapshot = ContextSnapshotModel()

    def get_snapshot(self) -> ContextSnapshotModel:
        return self._snapshot

    def update(self, **kwargs) -> None:
        updated_dict = self._snapshot.model_dump()
        updated_dict.update(kwargs)
        self._snapshot = ContextSnapshotModel(**updated_dict)
