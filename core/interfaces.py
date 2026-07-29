from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Awaitable, AsyncGenerator
from core.models import EventModel, ToolMetadata, ToolRequestModel, ToolResultModel, ExecutionContextModel

class IEventBus(ABC):
    @abstractmethod
    async def publish(self, event: EventModel) -> None:
        """Publishes an event asynchronously across the bus to all registered topic subscribers."""
        ...

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        """Registers an asynchronous event handler for a specific topic pattern."""
        ...

    @abstractmethod
    def unsubscribe(self, topic: str, handler: Callable[[EventModel], Awaitable[None]]) -> None:
        """Removes an event handler subscription."""
        ...

class IService(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique service identifier name."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Initializes and starts the service lifecycle."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stops the service cleanly during system shutdown."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Performs a health check returning True if operational."""
        ...

class ILLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generates text from natural language prompt input."""
        ...

    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Generates structured JSON output validated against system directives."""
        ...

class ISTTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> str:
        """Transcribes raw audio bytes into text."""
        ...

    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncGenerator[bytes, None], language: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Transcribes streaming audio chunks into text tokens asynchronously."""
        ...

class ITTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: Optional[str] = None, language: Optional[str] = None) -> bytes:
        """Synthesizes text into audio stream bytes."""
        ...

    @abstractmethod
    async def synthesize_stream(self, text_stream: AsyncGenerator[str, None], voice: Optional[str] = None, language: Optional[str] = None) -> AsyncGenerator[bytes, None]:
        """Synthesizes text stream tokens into audio chunks asynchronously."""
        ...

class ITool(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Returns tool metadata descriptor."""
        ...

    @abstractmethod
    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        """Executes tool request asynchronously."""
        ...

    @abstractmethod
    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        """Reverses previous tool execution."""
        ...

class ISkill(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill name."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Exposed capabilities."""
        ...

    @abstractmethod
    async def run(self, context: ExecutionContextModel) -> ToolResultModel:
        """Executes skill workflow returning typed ToolResultModel."""
        ...

class IPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        ...

    @abstractmethod
    async def on_load(self, container: Any) -> None:
        """Plugin initialization lifecycle callback."""
        ...

    @abstractmethod
    async def on_unload(self) -> None:
        """Plugin teardown lifecycle callback."""
        ...
