"""
tests/test_phase1.py — Integration and unit test suite for Phase 1 skeleton completion.
"""
import pytest
import asyncio
import uuid
import sys

from system.mode_manager import ModeManager, ModeProfileModel
from context.context_manager import ContextManager, ContextSnapshotModel
from models.stt import FasterWhisperSTTProvider
from models.tts import EdgeTTSProvider
from speech.speech_manager import SpeechManager
from language.manager import LanguageManager
from state.state_manager import StateManager
from tools.system_tools.applications import ApplicationLauncherTool, _APP_CATALOG


def test_mode_manager_profiles_integration():
    """Verify ModeManager real profile switching and listener notifications."""
    mm = ModeManager(initial_mode="Developer")
    assert mm.current_mode == "Developer"
    assert mm.active_profile.notification_level == "verbose"
    assert "vscode" in mm.active_profile.auto_launch_apps

    received_profiles = []
    def on_mode_change(profile: ModeProfileModel):
        received_profiles.append(profile)

    mm.add_listener(on_mode_change)
    assert mm.set_mode("Gaming") is True
    assert mm.current_mode == "Gaming"
    assert len(received_profiles) == 1
    assert received_profiles[0].notification_level == "silent"


def test_app_catalog_expansion():
    """Verify expanded application catalog contains newly added software entries."""
    tool = ApplicationLauncherTool()
    assert "steam" in _APP_CATALOG
    assert "zoom" in _APP_CATALOG
    assert "brave" in _APP_CATALOG
    assert "control panel" in _APP_CATALOG


@pytest.mark.asyncio
async def test_stt_fallback_integration():
    """Verify STT provider fallback behavior when primary model is missing/fails."""
    stt = FasterWhisperSTTProvider()
    res = await stt.transcribe(b"NON_EMPTY_PCM_BYTES_TEST")
    assert isinstance(res, str)


@pytest.mark.asyncio
async def test_tts_fallback_integration():
    """Verify TTS provider fallback synthesis when edge-tts is missing/fails."""
    tts = EdgeTTSProvider()
    res = await tts.synthesize("Testing TTS fallback")
    assert isinstance(res, bytes)


@pytest.mark.asyncio
async def test_context_manager_snapshot_windows():
    """Verify ContextManager snapshot generation on real OS environment."""
    cm = ContextManager()
    snapshot = cm.get_snapshot()
    assert isinstance(snapshot, ContextSnapshotModel)
    assert hasattr(snapshot, "focused_app")
    assert hasattr(snapshot, "active_mode")
