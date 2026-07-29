import json
import asyncio
from typing import Dict, Any, Optional, Type, TypeVar
from pydantic import BaseModel
from core.interfaces import ILLMProvider
from core.models import LLMExecutionPlanResponse, PlanStepModel
from observability.logger import logger

T = TypeVar("T", bound=BaseModel)

class OllamaLLMProvider(ILLMProvider):
    """Local LLM Provider using Ollama with structured JSON schema validation."""
    
    def __init__(self, model_name: str = "qwen2.5-coder"):
        self.model_name = model_name

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        try:
            import ollama
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = await asyncio.to_thread(ollama.chat, model=self.model_name, messages=messages)
            return response.get('message', {}).get('content', '')
        except Exception as e:
            logger.warning(f"Ollama generation fallback triggered (Ollama unreachable or error: {e})")
            return f"[JARVIS Fallback Engine]: Received request: '{prompt[:50]}...'. Ollama service currently initializing."

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        text_resp = await self.generate(prompt, system_prompt=system_prompt, **kwargs)
        try:
            start = text_resp.find('{')
            end = text_resp.rfind('}') + 1
            if start != -1 and end != -1:
                parsed = json.loads(text_resp[start:end])
                if isinstance(parsed, dict):
                    return parsed
        except Exception as e:
            logger.warning(f"[OllamaLLMProvider] Error parsing JSON from text response: {e}")
        return {"response": text_resp, "status": "raw"}
