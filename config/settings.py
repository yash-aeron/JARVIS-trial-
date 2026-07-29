import os
import yaml
from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel, Field

class ProfileConfigModel(BaseModel):
    profile_name: str = "Developer"
    logging_verbosity: str = "INFO"
    allow_tool_execution: bool = True
    vram_budget_mb: float = 3500.0

class Settings:
    """Configuration Manager supporting Pydantic profiles, dynamic updates, and validation."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.config_dir = self.base_dir / "config"
        self.profiles_dir = self.config_dir / "profiles"
        self._config: ProfileConfigModel = ProfileConfigModel()
        self._active_profile_name: str = "Developer"
        
        self.reload()

    def reload(self) -> None:
        config_path = self.config_dir / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}
                self._config = ProfileConfigModel(
                    profile_name=raw_data.get("system", {}).get("default_profile", "Developer")
                )
        else:
            self._config = ProfileConfigModel(profile_name="Developer")
            
        self.switch_profile(self._config.profile_name)

    def switch_profile(self, profile_name: str) -> bool:
        profile_path = self.profiles_dir / f"{profile_name}.yaml"
        if profile_path.exists():
            with open(profile_path, "r", encoding="utf-8") as f:
                raw_profile = yaml.safe_load(f) or {}
                self._config = ProfileConfigModel(
                    profile_name=profile_name,
                    logging_verbosity=raw_profile.get("logging_verbosity", "INFO"),
                    allow_tool_execution=raw_profile.get("allow_tool_execution", True),
                    vram_budget_mb=float(raw_profile.get("vram_budget_mb", 3500.0))
                )
                self._active_profile_name = profile_name
                return True
        return False

    def get(self, key_path: str, default: Any = None) -> Any:
        if key_path == "models.stt_provider":
            return "whisper"
        elif key_path == "models.tts_provider":
            return "edge-tts"
        elif key_path == "models.llm_provider":
            return "ollama"
        elif key_path == "models.llm_model":
            return "qwen2.5-coder"
        return default

    @property
    def profile_name(self) -> str:
        return self._active_profile_name

    @property
    def active_profile(self) -> ProfileConfigModel:
        return self._config
