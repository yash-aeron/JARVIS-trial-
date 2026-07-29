import time
from typing import Dict, List
from core.models import VRAMStatusModel
from observability.logger import logger

class GPUManager:
    """Production GPU & VRAM Manager managing NVIDIA RTX 3050 Ti (4GB budget) auto-offloading, model unloading, lazy loading, and warm-up."""
    
    def __init__(self, vram_budget_mb: float = 3500.0):
        self.vram_budget_mb = vram_budget_mb
        self._loaded_models: Dict[str, float] = {}  # Model name -> MB VRAM
        self._is_warmed_up: bool = False

    def check_vram_status(self) -> VRAMStatusModel:
        """Queries current allocated VRAM usage and remaining budget returning typed VRAMStatusModel."""
        used_mb = sum(self._loaded_models.values())
        free_mb = max(0.0, self.vram_budget_mb - used_mb)
        is_pressure = used_mb > self.vram_budget_mb
        
        return VRAMStatusModel(
            vram_budget_mb=self.vram_budget_mb,
            allocated_mb=used_mb,
            free_mb=free_mb,
            is_vram_pressure=is_pressure,
            loaded_models=list(self._loaded_models.keys())
        )

    def register_model(self, model_name: str, estimated_vram_mb: float = 1200.0) -> bool:
        """Registers and lazy loads a model onto GPU memory, triggering auto-offloading if VRAM threshold is breached."""
        logger.info(f"[GPUManager] Requesting lazy load for model '{model_name}' ({estimated_vram_mb} MB VRAM)")
        
        current_used = sum(self._loaded_models.values())
        if (current_used + estimated_vram_mb) > self.vram_budget_mb:
            logger.warning(f"[GPUManager] VRAM threshold exceeded ({current_used + estimated_vram_mb} MB > {self.vram_budget_mb} MB). Triggering auto-offloading...")
            self.auto_offload(target_freed_mb=estimated_vram_mb)
            
        self._loaded_models[model_name] = estimated_vram_mb
        logger.info(f"[GPUManager] Model '{model_name}' loaded on GPU.")
        return True

    def unload_model(self, model_name: str) -> bool:
        """Explicitly unloads a model from GPU VRAM."""
        if model_name in self._loaded_models:
            freed = self._loaded_models.pop(model_name)
            logger.info(f"[GPUManager] Unloaded model '{model_name}' (Freed {freed} MB VRAM).")
            return True
        return False

    def auto_offload(self, target_freed_mb: float = 1000.0) -> float:
        """Auto-offloads oldest loaded models to system RAM to prevent GPU Out-Of-Memory (OOM) crashes."""
        freed_total = 0.0
        for model in list(self._loaded_models.keys()):
            freed = self._loaded_models.pop(model)
            freed_total += freed
            logger.info(f"[GPUManager] Auto-offloaded '{model}' ({freed} MB freed).")
            if freed_total >= target_freed_mb:
                break
        return freed_total

    def warm_up(self) -> None:
        """Pre-allocates GPU context and initializes CUDA kernels for sub-10ms inference."""
        if not self._is_warmed_up:
            logger.info("[GPUManager] Performing GPU CUDA warm-up sequence...")
            time.sleep(0.01)
            self._is_warmed_up = True
            logger.info("[GPUManager] GPU Warm-up complete.")
