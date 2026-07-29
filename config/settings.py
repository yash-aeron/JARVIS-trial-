import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

class Settings:
    """Configuration Manager supporting profiles, dynamic updates, and validation."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.config_dir = self.base_dir / "config"
        self.profiles_dir = self.config_dir / "profiles"
        self._config: Dict[str, Any] = {}
        self._active_profile: Dict[str, Any] = {}
        self._active_profile_name: str = "Developer"
        
        self.reload()

    def reload(self) -> None:
        config_path = self.config_dir / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {
                "system": {"name": "JARVIS", "version": "1.0.0", "default_profile": "Developer"},
                "models": {"llm_provider": "ollama", "llm_model": "qwen2.5-coder"}
            }
            
        profile_name = self._config.get("system", {}).get("default_profile", "Developer")
        self.switch_profile(profile_name)

    def switch_profile(self, profile_name: str) -> bool:
        profile_path = self.profiles_dir / f"{profile_name}.yaml"
        if profile_path.exists():
            with open(profile_path, "r", encoding="utf-8") as f:
                self._active_profile = yaml.safe_load(f) or {}
                self._active_profile_name = profile_name
                return True
        return False

    def get(self, key_path: str, default: Any = None) -> Any:
        keys = key_path.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    @property
    def profile_name(self) -> str:
        return self._active_profile_name

    @property
    def active_profile(self) -> Dict[str, Any]:
        return self._active_profile
