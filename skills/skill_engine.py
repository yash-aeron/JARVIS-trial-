from typing import Dict, Any, List, Optional
from core.interfaces import ISkill, ITool
from tools.registry import ToolRegistry
from observability.logger import logger

class CodingSkill(ISkill):
    """Composite skill providing coding workflow (VS Code, Git, Terminal execution)."""
    
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "CodingSkill"

    @property
    def capabilities(self) -> List[str]:
        return ["coding_environment", "git_automation", "terminal_execution"]

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[CodingSkill] Executing coding environment workflow...")
        launcher = self.tool_registry.get("app_launcher")
        if launcher:
            await launcher.execute(app_name="VS Code", action="launch")
        return {"status": "success", "skill": self.name, "message": "Coding environment ready."}

class SkillEngine:
    """Registry and execution orchestrator for composite skills."""
    
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self._skills: Dict[str, ISkill] = {}
        
        # Register default skills
        self.register_skill(CodingSkill(tool_registry))

    def register_skill(self, skill: ISkill) -> None:
        self._skills[skill.name] = skill
        logger.info(f"Registered skill '{skill.name}'")

    def get_skill(self, name: str) -> Optional[ISkill]:
        return self._skills.get(name)

    def list_skills(self) -> List[str]:
        return list(self._skills.keys())
