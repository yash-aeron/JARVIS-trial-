from system.monitor import SystemMonitor
from core.models import SystemStatusModel

class Diagnostics:
    """Provides system diagnostics and hardware resource metrics."""
    
    def __init__(self):
        self.monitor = SystemMonitor()

    def get_system_snapshot(self) -> SystemStatusModel:
        return self.monitor.get_stats()
