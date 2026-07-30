import os
import re
from typing import Dict
from observability.logger import logger

# Markdown templates use {{name}}; the built-in fallbacks use {name}. Support both.
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}|\{(\w+)\}")

class PromptManager:
    """Markdown prompt manager with in-memory template caching to eliminate repeated disk reads."""

    def __init__(self, prompt_dir: str = "prompts"):
        self.prompt_dir = prompt_dir
        self._cache: Dict[str, str] = {}

    def get(self, template_name: str, **kwargs) -> str:
        """Fetches markdown prompt template from cache or disk, parameterizing with kwargs."""
        if template_name not in self._cache:
            file_path = os.path.join(self.prompt_dir, f"{template_name}.md")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    self._cache[template_name] = f.read()
                logger.info(f"[PromptManager] Cached prompt template '{template_name}' from disk.")
            else:
                # Default fallback templates if markdown file is missing
                if template_name == "intent":
                    self._cache[template_name] = "Classify the following user input: {input}"
                elif template_name == "planner":
                    self._cache[template_name] = "Create execution plan for goal '{goal}' using capabilities: {capabilities}"
                else:
                    self._cache[template_name] = "Process user request: {input}"

        template = self._cache[template_name]
        missing: list[str] = []

        def substitute(match: re.Match) -> str:
            name = match.group(1) or match.group(2)
            if name in kwargs:
                return str(kwargs[name])
            missing.append(name)
            return match.group(0)

        rendered = _PLACEHOLDER.sub(substitute, template)
        if missing:
            logger.warning(
                f"[PromptManager] Prompt '{template_name}' has unfilled variable(s): {sorted(set(missing))}"
            )
        return rendered
