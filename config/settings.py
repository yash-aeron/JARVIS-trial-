import yaml
from pathlib import Path
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field

class ProfileConfigModel(BaseModel):
    profile_name: str = "Developer"
    description: str = ""
    permissions: Dict[str, Any] = Field(default_factory=dict)
    active_modes: List[str] = Field(default_factory=list)
    vram_budget_mb: float = 3500.0
    auto_unload_llm: bool = False
    speech_enabled: bool = True
    dashboard_layout: str = "developer_full"

    @property
    def default_permission_level(self) -> str:
        return str(self.permissions.get("default_level", "MEDIUM"))

class Settings:
    """Configuration Manager supporting Pydantic profiles, dynamic updates, and validation."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).parent.parent
        self.config_dir = self.base_dir / "config"
        self.profiles_dir = self.config_dir / "profiles"
        self._raw_config: Dict[str, Any] = {}
        self._config: ProfileConfigModel = ProfileConfigModel()
        self._active_profile_name: str = "Developer"

        self.reload()

    def reload(self) -> None:
        config_path = self.config_dir / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._raw_config = yaml.safe_load(f) or {}
        else:
            self._raw_config = {}

        default_profile = self._raw_config.get("system", {}).get("default_profile", "Developer")
        if not self.switch_profile(default_profile):
            self._config = ProfileConfigModel(profile_name=default_profile)
            self._active_profile_name = default_profile

    def switch_profile(self, profile_name: str) -> bool:
        profile_path = self.profiles_dir / f"{profile_name}.yaml"
        if not profile_path.exists():
            return False

        with open(profile_path, "r", encoding="utf-8") as f:
            raw_profile = yaml.safe_load(f) or {}

        # Profile YAMLs express the budget in GB; the model tracks MB.
        vram_gb = raw_profile.get("vram_budget_gb")
        vram_mb = float(vram_gb) * 1024.0 if vram_gb is not None else 3500.0

        self._config = ProfileConfigModel(
            profile_name=raw_profile.get("profile_name", profile_name),
            description=raw_profile.get("description", ""),
            permissions=raw_profile.get("permissions", {}) or {},
            active_modes=raw_profile.get("active_modes", []) or [],
            vram_budget_mb=vram_mb,
            auto_unload_llm=bool(raw_profile.get("auto_unload_llm", False)),
            speech_enabled=bool(raw_profile.get("speech_enabled", True)),
            dashboard_layout=raw_profile.get("dashboard_layout", "developer_full"),
        )
        self._active_profile_name = profile_name
        return True

    def get(self, key_path: str, default: Any = None) -> Any:
        """Resolve a dotted path (e.g. 'models.llm_provider') against config.yaml."""
        node: Any = self._raw_config
        for part in key_path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def profile_name(self) -> str:
        return self._active_profile_name

    @property
    def active_profile(self) -> ProfileConfigModel:
        return self._config
