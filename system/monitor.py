import psutil
from typing import Dict, Any

class SystemMonitor:
    """Hardware monitoring engine for CPU, RAM, Disk, and System stats."""
    
    def get_stats(self) -> Dict[str, Any]:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "disk_percent": disk.percent
        }
