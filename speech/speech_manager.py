import asyncio
import uuid
from typing import Optional, Dict, Any
from core.interfaces import IService, ISTTProvider, ITTSProvider, IEventBus
from core.models import EventModel, SpeechRecognizedEventData, SpeechSpokeEventData
from state.state_manager import StateManager
from state.states import AssistantState
from language.manager import LanguageManager
from observability.logger import logger

class SpeechManager(IService):
    """Speech Orchestrator driving STT/TTS providers resolved via DI with typed EventModel payloads."""
    
    def __init__(
        self, 
        stt: ISTTProvider, 
        tts: ITTSProvider, 
        language_manager: LanguageManager,
        state_manager: StateManager,
        event_bus: Optional[IEventBus] = None
    ):
        self._stt = stt
        self._tts = tts
        self._language_manager = language_manager
        self._state_manager = state_manager
        self._event_bus = event_bus

    @property
    def name(self) -> str:
        return "SpeechManager"

    async def start(self) -> None:
        logger.info("SpeechManager started.")

    async def stop(self) -> None:
        logger.info("SpeechManager stopped.")

    async def health_check(self) -> bool:
        return True

    async def process_speech_input(self, audio_data: bytes, correlation_id: Optional[str] = None) -> str:
        cid = correlation_id or str(uuid.uuid4())
        self._state_manager.transition_to(AssistantState.LISTENING, "Speech input received", correlation_id=cid)
        
        text = await self._stt.transcribe(audio_data, language=self._language_manager.active_language)
        lang_res = self._language_manager.process_utterance(text)
        
        if self._event_bus:
            payload = SpeechRecognizedEventData(text=text, language_details=lang_res)
            await self._event_bus.publish(
                EventModel(
                    correlation_id=cid,
                    topic="speech.recognized",
                    payload=payload,
                    sender="SpeechManager"
                )
            )
            
        return text

    async def speak(self, text: str, language: Optional[str] = None, correlation_id: Optional[str] = None) -> None:
        cid = correlation_id or str(uuid.uuid4())
        self._state_manager.transition_to(AssistantState.SPEAKING, "Synthesizing speech", correlation_id=cid)
        voice = self._language_manager.get_voice_for_language(language)
        
        audio_bytes = await self._tts.synthesize(text, voice=voice, language=language)
        
        if self._event_bus:
            payload = SpeechSpokeEventData(text=text, voice=voice, audio_length=len(audio_bytes))
            await self._event_bus.publish(
                EventModel(
                    correlation_id=cid,
                    topic="speech.spoke",
                    payload=payload,
                    sender="SpeechManager"
                )
            )
            
        self._state_manager.transition_to(AssistantState.IDLE, "Speech completed", correlation_id=cid)
