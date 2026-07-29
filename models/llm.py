"""
models/llm.py — Production Local LLM Router & Ollama Provider.

Provides:
  - TaskComplexity: Enum classifying task scope (SIMPLE_INTENT, MULTI_STEP_PLAN, LONG_FORM_REASONING).
  - LLMRouter: Internal model router selecting tiered local models (small, medium, large).
  - OllamaLLMProvider: Conforming to ILLMProvider interface with internal intelligent model routing.
"""
import json
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Type, TypeVar, List
from pydantic import BaseModel
from core.interfaces import ILLMProvider
from core.models import LLMExecutionPlanResponse, PlanStepModel
from observability.logger import logger

T = TypeVar("T", bound=BaseModel)


class TaskComplexity(str, Enum):
    SIMPLE_INTENT = "SIMPLE_INTENT"
    MULTI_STEP_PLAN = "MULTI_STEP_PLAN"
    LONG_FORM_REASONING = "LONG_FORM_REASONING"


class LLMRouter:
    """Classifies task complexity and selects tiered local models dynamically."""

    def __init__(
        self,
        small_model: str = "qwen2.5-coder:0.5b",
        medium_model: str = "qwen2.5-coder:7b",
        large_model: str = "qwen2.5-coder:14b"
    ):
        self.small_model = small_model
        self.medium_model = medium_model
        self.large_model = large_model

    def classify_complexity(self, prompt: str, system_prompt: Optional[str] = None) -> TaskComplexity:
        combined = f"{system_prompt or ''} {prompt}".lower()
        if len(prompt) > 500 or "analyze" in combined or "deconstruct" in combined or "reason" in combined:
            return TaskComplexity.LONG_FORM_REASONING
        if "plan" in combined or "steps" in combined or "and" in combined or "then" in combined or "json" in combined:
            return TaskComplexity.MULTI_STEP_PLAN
        return TaskComplexity.SIMPLE_INTENT

    def select_model(self, complexity: TaskComplexity, available_models: Optional[List[str]] = None) -> str:
        target = self.medium_model
        if complexity == TaskComplexity.SIMPLE_INTENT:
            target = self.small_model
        elif complexity == TaskComplexity.LONG_FORM_REASONING:
            target = self.large_model

        if available_models:
            # Fallback to closest available model if target is not pulled
            for m in [target, self.medium_model, self.small_model, "qwen2.5-coder"]:
                if any(m in name for name in available_models):
                    return m
            return available_models[0]
        return target


class OllamaLLMProvider(ILLMProvider):
    """Local LLM Provider using Ollama with internal dynamic model routing."""

    def __init__(
        self,
        model_name: str = "qwen2.5-coder",
        router: Optional[LLMRouter] = None
    ):
        self.default_model_name = model_name
        self.router = router or LLMRouter()
        self._available_models: List[str] = []

    async def _fetch_available_models(self) -> List[str]:
        try:
            import ollama
            res = await asyncio.to_thread(ollama.list)
            models = res.get("models", [])
            names = [m.get("name", "") for m in models]
            self._available_models = names
            return names
        except Exception:
            return []

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        complexity = self.router.classify_complexity(prompt, system_prompt)
        selected_model = kwargs.get("model") or self.router.select_model(complexity, self._available_models)
        logger.info(f"[LLMRouter] Routed prompt to model '{selected_model}' [Complexity: {complexity.value}]")

        try:
            import ollama
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await asyncio.to_thread(ollama.chat, model=selected_model, messages=messages)
            return response.get('message', {}).get('content', '')
        except Exception as e:
            logger.warning(f"Ollama generation fallback triggered for model '{selected_model}' (Error: {e})")
            return f"[JARVIS Fallback Engine]: Received request: '{prompt[:50]}...'. Ollama service initializing."

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
            logger.warning(f"[OllamaLLMProvider] Error parsing JSON response: {e}")
        return {"response": text_resp, "status": "raw"}
