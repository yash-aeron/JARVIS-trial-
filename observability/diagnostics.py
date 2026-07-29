import psutil
from typing import Dict, Any

class SystemDiagnostics:
    """Collects system health diagnostics, crash traces, and stack info."""
    
    @staticmethod
    def get_system_snapshot() -> Dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu_percent,
            "ram_used_gb": round(memory.used / (1024**3), 2),
            "ram_total_gb": round(memory.total / (1024**3), 2),
            "ram_percent": memory.percent,
            "disk_percent": disk.percent
        }
