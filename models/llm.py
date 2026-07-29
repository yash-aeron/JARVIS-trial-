import json
import asyncio
from typing import Dict, Any, Optional
from core.interfaces import ILLMProvider
from observability.logger import logger

class OllamaLLMProvider(ILLMProvider):
    """Local LLM Provider using Ollama with automatic mock fallback if service is unavailable."""
    
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
            # Simple JSON extraction regex/parser
            start = text_resp.find('{')
            end = text_resp.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(text_resp[start:end])
        except Exception:
            pass
        return {"response": text_resp, "status": "raw"}
