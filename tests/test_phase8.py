"""
tests/test_phase8.py — Unit and integration tests for Phase 8 Local LLM Routing.
"""
import pytest
from models.llm import TaskComplexity, LLMRouter, OllamaLLMProvider


def test_task_complexity_classification():
    """Verify LLMRouter prompt classification into task complexity categories."""
    router = LLMRouter()

    # Simple intent
    comp_simple = router.classify_complexity("Open Chrome")
    assert comp_simple == TaskComplexity.SIMPLE_INTENT

    # Multi-step plan
    comp_plan = router.classify_complexity("Open Chrome and launch VS Code then check system status")
    assert comp_plan == TaskComplexity.MULTI_STEP_PLAN

    # Long-form reasoning
    long_prompt = "Analyze system log telemetry, deconstruct root cause exceptions, and reason through potential fixes."
    comp_reasoning = router.classify_complexity(long_prompt)
    assert comp_reasoning == TaskComplexity.LONG_FORM_REASONING


def test_model_selection_fallback():
    """Verify LLMRouter model selection with available model fallback matching."""
    router = LLMRouter(small_model="qwen2.5-coder:0.5b", medium_model="qwen2.5-coder:7b", large_model="qwen2.5-coder:14b")

    # Target model selection without pulled model constraint
    assert router.select_model(TaskComplexity.SIMPLE_INTENT) == "qwen2.5-coder:0.5b"
    assert router.select_model(TaskComplexity.MULTI_STEP_PLAN) == "qwen2.5-coder:7b"
    assert router.select_model(TaskComplexity.LONG_FORM_REASONING) == "qwen2.5-coder:14b"

    # Selection with available pulled models list
    available = ["qwen2.5-coder:7b", "llama3:latest"]
    selected = router.select_model(TaskComplexity.LONG_FORM_REASONING, available_models=available)
    assert selected == "qwen2.5-coder:7b"


@pytest.mark.asyncio
async def test_ollama_llm_provider_routing_integration():
    """Verify OllamaLLMProvider encapsulates LLMRouter while maintaining ILLMProvider interface."""
    provider = OllamaLLMProvider()
    resp = await provider.generate("Open Notepad")

    assert isinstance(resp, str)
    assert len(resp) > 0
