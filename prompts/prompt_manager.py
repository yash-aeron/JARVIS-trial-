from pathlib import Path
from typing import Dict, Any, Optional

class PromptManager:
    """Centralized manager for loading, caching, versioning, and parameterizing Markdown prompts."""
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or Path(__file__).parent
        self._cache: Dict[str, str] = {}

    def get(self, prompt_name: str, **kwargs) -> str:
        if prompt_name not in self._cache:
            file_path = self.prompts_dir / f"{prompt_name}.md"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    self._cache[prompt_name] = f.read()
            else:
                self._cache[prompt_name] = f"# Default {prompt_name} Prompt\nProcess request."
                
        template = self._cache[prompt_name]
        for key, val in kwargs.items():
            template = template.replace(f"{{{{{key}}}}}", str(val))
        return template

    def clear_cache(self) -> None:
        self._cache.clear()
