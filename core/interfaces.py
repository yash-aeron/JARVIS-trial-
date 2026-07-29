from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Awaitable
from core.models import EventModel, ToolMetadata, ToolRequestModel, ToolResultModel

class IEventBus(ABC):
    @abstractmethod
    async def publish(self, event: EventModel) -> None:
        pass

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        pass

    @abstractmethod
    def unsubscribe(self, topic: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        pass

class IService(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

class ILLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        pass

class ISTTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        pass

class ITTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: Optional[str] = None, language: Optional[str] = None) -> bytes:
        pass

class ITool(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        pass

    @abstractmethod
    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        pass

    @abstractmethod
    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        pass

class ISkill(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        pass

    @abstractmethod
    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass

class IPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        pass

    @abstractmethod
    async def on_load(self, container: Any) -> None:
        pass

    @abstractmethod
    async def on_unload(self) -> None:
        pass
