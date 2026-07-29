import uuid
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class SessionModel(BaseModel):
    session_id: str = Field(default_factory=lambda: f"sess_{int(datetime.now().timestamp())}")
    session_name: str
    start_time: float = Field(default_factory=lambda: datetime.now().timestamp())
    tasks_performed: List[str] = Field(default_factory=list)
    is_active: bool = True

class SessionManager:
    """Manages session lifecycles (Morning Session, Coding Session, Focus Session) & archival."""
    
    def __init__(self):
        self._active_session: Optional[SessionModel] = None
        self._archived_sessions: List[SessionModel] = []
        self.start_session("Default Session")

    def start_session(self, name: str) -> SessionModel:
        if self._active_session:
            self._active_session.is_active = False
            self._archived_sessions.append(self._active_session)
            
        session = SessionModel(session_name=name)
        self._active_session = session
        return session

    @property
    def current_session(self) -> Optional[SessionModel]:
        return self._active_session
