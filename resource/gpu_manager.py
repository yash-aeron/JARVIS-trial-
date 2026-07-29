import psutil
from typing import Dict, Any, Optional
from observability.logger import logger

class GPUManager:
    """VRAM budget controller and model offloading helper optimized for GPUs (e.g., RTX 3050 Ti 4GB)."""
    
    def __init__(self, max_vram_gb: float = 4.0):
        self.max_vram_gb = max_vram_gb
        self.allocated_vram_gb = 0.0

    def request_vram(self, required_gb: float) -> bool:
        if self.allocated_vram_gb + required_gb <= self.max_vram_gb:
            self.allocated_vram_gb += required_gb
            logger.info(f"Allocated {required_gb}GB VRAM. Total active VRAM: {self.allocated_vram_gb:.2f}GB / {self.max_vram_gb}GB")
            return True
        logger.warning(f"VRAM budget exceeded! Requested: {required_gb}GB, Available: {self.max_vram_gb - self.allocated_vram_gb:.2f}GB")
        return False

    def release_vram(self, released_gb: float) -> None:
        self.allocated_vram_gb = max(0.0, self.allocated_vram_gb - released_gb)
        logger.info(f"Released {released_gb}GB VRAM. Current total: {self.allocated_vram_gb:.2f}GB")
