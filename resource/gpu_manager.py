import psutil
from typing import Dict, Any, Optional, List
from observability.logger import logger

class GPUManager:
    """VRAM budget controller and proactive model offloading manager optimized for GPUs (e.g., NVIDIA RTX 3050 Ti 4GB VRAM budget)."""
    
    def __init__(self, max_vram_gb: float = 4.0, threshold_gb: float = 3.5):
        self.max_vram_gb = max_vram_gb
        self.threshold_gb = threshold_gb
        self.allocated_vram_gb = 0.0
        self._loaded_models: Dict[str, float] = {}

    def register_model_vram(self, model_name: str, size_gb: float) -> bool:
        if self.allocated_vram_gb + size_gb > self.threshold_gb:
            logger.warning(f"[GPUManager] Approaching 4GB VRAM limit ({self.allocated_vram_gb:.2f}GB / {self.max_vram_gb}GB). Proactively offloading inactive models...")
            self.auto_offload_inactive()
            
        if self.allocated_vram_gb + size_gb <= self.max_vram_gb:
            self.allocated_vram_gb += size_gb
            self._loaded_models[model_name] = size_gb
            logger.info(f"[GPUManager] Allocated {size_gb:.2f}GB VRAM for model '{model_name}'. Active VRAM: {self.allocated_vram_gb:.2f}GB / {self.max_vram_gb}GB")
            return True
            
        logger.error(f"[GPUManager] Out of VRAM! Required: {size_gb}GB, Available: {self.max_vram_gb - self.allocated_vram_gb:.2f}GB")
        return False

    def release_model_vram(self, model_name: str) -> None:
        if model_name in self._loaded_models:
            size_gb = self._loaded_models.pop(model_name)
            self.allocated_vram_gb = max(0.0, self.allocated_vram_gb - size_gb)
            logger.info(f"[GPUManager] Released {size_gb:.2f}GB VRAM for model '{model_name}'. Current active: {self.allocated_vram_gb:.2f}GB")

    def auto_offload_inactive(self) -> None:
        """Unloads inactive models when VRAM allocation approaches the 3.5GB threshold."""
        for name in list(self._loaded_models.keys()):
            self.release_model_vram(name)
            if self.allocated_vram_gb <= 2.0:
                break
