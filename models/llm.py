"""
models/llm.py — Production Local LLM Router & Ollama Provider.

Provides:
  - TaskComplexity: Enum classifying task scope (SIMPLE_INTENT, MULTI_STEP_PLAN, LONG_FORM_REASONING).
  - LLMRouter: Internal model router selecting tiered local models (small, medium, large).
  - OllamaLLMProvider: Conforming to ILLMProvider interface with internal intelligent model routing.
"""
import json
import re
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Type, TypeVar, List
from pydantic import BaseModel
from core.interfaces import ILLMProvider
from core.models import LLMExecutionPlanResponse, PlanStepModel
from observability.logger import logger

T = TypeVar("T", bound=BaseModel)

# Models routinely wrap JSON in ```json fences despite instructions not to.
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Pull a JSON object out of a raw LLM response.

    Handles code fences and bare top-level arrays (a common model output), which
    are normalized to {"steps": [...]} so the plan validator can consume them.
    """
    if not text:
        return None

    candidates: List[str] = []
    for m in _FENCE_RE.finditer(text):
        candidates.append(m.group(1).strip())
    candidates.append(text.strip())

    for raw in candidates:
        for start_ch, end_ch in (("{", "}"), ("[", "]")):
            start = raw.find(start_ch)
            end = raw.rfind(end_ch) + 1
            if start == -1 or end <= start:
                continue
            try:
                parsed = json.loads(raw[start:end])
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"steps": parsed}
    return None


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
        # 14B does not fit in a 4 GB consumer GPU; the 7B is the largest tier that
        # runs locally, and select_model degrades to what is actually installed.
        large_model: str = "qwen2.5-coder:7b"
    ):
        self.small_model = small_model
        self.medium_model = medium_model
        self.large_model = large_model

    def classify_complexity(self, prompt: str, system_prompt: Optional[str] = None) -> TaskComplexity:
        combined = f"{system_prompt or ''} {prompt}".lower()
        # Length alone is a poor signal: the planner template is ~1.4k chars for even
        # a trivial goal, which previously forced every request to the largest tier.
        if any(w in combined for w in ("analyze", "deconstruct", "reason about", "explain why")):
            return TaskComplexity.LONG_FORM_REASONING
        if any(w in combined for w in ("plan", "steps", "json", " then ")):
            return TaskComplexity.MULTI_STEP_PLAN
        if len(prompt) > 2000:
            return TaskComplexity.LONG_FORM_REASONING
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
            models = getattr(res, "models", None)
            if models is None:
                models = res.get("models", []) if hasattr(res, "get") else []
            names: List[str] = []
            for m in models:
                # Modern ollama clients expose `.model`; older ones used a "name" key.
                name = getattr(m, "model", None)
                if not name and hasattr(m, "get"):
                    name = m.get("model") or m.get("name")
                if name:
                    names.append(name)
            self._available_models = names
            return names
        except Exception as e:
            logger.warning(f"[OllamaLLMProvider] Could not list local models: {e}")
            return []

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        hint = kwargs.get("complexity_hint")
        complexity = hint if isinstance(hint, TaskComplexity) else self.router.classify_complexity(prompt, system_prompt)

        # Discover installed models once, so routing can degrade to what is actually
        # pulled instead of requesting a tier that was never downloaded.
        if not self._available_models:
            await self._fetch_available_models()
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
        parsed = _extract_json(text_resp)
        if parsed is not None:
            return parsed
        logger.warning("[OllamaLLMProvider] Could not extract JSON from model response.")
        return {"response": text_resp, "status": "raw"}
