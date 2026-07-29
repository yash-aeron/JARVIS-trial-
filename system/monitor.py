import psutil
from core.models import SystemStatusModel

class SystemMonitor:
    """Monitors local system resource utilization (CPU, RAM, Disk)."""
    
    def get_stats(self) -> SystemStatusModel:
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return SystemStatusModel(
            cpu_percent=cpu,
            ram_percent=memory.percent,
            disk_percent=disk.percent
        )
