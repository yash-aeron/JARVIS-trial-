"""
tests/test_phase10.py — Integration test suite for Phase 10 Benchmarking & Testing Depth.
Includes end-to-end scripted voice-command test pipeline (mocking audio hardware).
"""
import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock

from core.app import JARVISApp, bootstrap_container
from core.interfaces import ISTTProvider, ITTSProvider, IEventBus
from core.models import UserCommandResultModel, EventModel, SpeechRecognizedEventData
from benchmark.benchmarking import SystemBenchmarking
from benchmark.benchmark_ci import main as run_ci_benchmark


@pytest.mark.asyncio
async def test_end_to_end_scripted_voice_command_pipeline():
    """Scripted E2E Voice-Command Test Pipeline (mocking physical audio hardware)."""
    container = bootstrap_container()

    # Mock audio hardware STT/TTS providers
    mock_stt = AsyncMock(spec=ISTTProvider)
    mock_stt.transcribe.return_value = "Open Chrome and launch VS Code"

    mock_tts = AsyncMock(spec=ITTSProvider)
    mock_tts.synthesize.return_value = b"\x00" * 100

    container.register_singleton(ISTTProvider, mock_stt)
    container.register_singleton(ITTSProvider, mock_tts)

    app = JARVISApp(container=container)
    await app.initialize()

    # Simulate voice recognition event payload trigger
    event_bus: IEventBus = container.resolve(IEventBus)
    cid = f"cid_voice_e2e_{uuid.uuid4()}"

    recognized_event = EventModel(
        correlation_id=cid,
        topic="speech.recognized",
        sender="SpeechManager",
        payload=SpeechRecognizedEventData(text="Open Chrome and launch VS Code")
    )
    await event_bus.publish(recognized_event)

    # Process user command through master orchestrator
    result: UserCommandResultModel = await app.process_user_command("Open Chrome and launch VS Code")

    assert result.correlation_id is not None
    assert len(result.execution_results) >= 1

    await app.shutdown()


@pytest.mark.asyncio
async def test_real_benchmarking_runner_and_sla_ci_check():
    """Verify real benchmark latency execution and SLA threshold pass in CI."""
    bench = SystemBenchmarking()
    res = await bench.run_all_benchmarks()

    assert res.startup_time_ms >= 0.0
    assert res.planner_latency_ms >= 0.0
    assert res.executor_latency_ms >= 0.0
    assert res.stt_latency_ms >= 0.0
    assert res.tts_latency_ms >= 0.0

    # Run CI runner entry point
    exit_code = await run_ci_benchmark()
    assert exit_code == 0
