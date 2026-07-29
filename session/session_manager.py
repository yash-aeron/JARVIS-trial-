from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

@dataclass
class Session:
    session_id: str
    session_name: str
    start_time: float = field(default_factory=lambda: datetime.now().timestamp())
    tasks_performed: List[str] = field(default_factory=list)
    is_active: bool = True

class SessionManager:
    """Manages session lifecycles (Morning Session, Coding Session, Focus Session) & archival."""
    
    def __init__(self):
        self._active_session: Optional[Session] = None
        self._archived_sessions: List[Session] = []
        self.start_session("Default Session")

    def start_session(self, name: str) -> Session:
        if self._active_session:
            self._active_session.is_active = False
            self._archived_sessions.append(self._active_session)
            
        session = Session(session_id=f"sess_{int(datetime.now().timestamp())}", session_name=name)
        self._active_session = session
        return session

    @property
    def current_session(self) -> Optional[Session]:
        return self._active_session
