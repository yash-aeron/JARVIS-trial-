"""
tests/test_phase5.py — Unit and integration tests for Phase 5 Vision & Desktop Understanding.
"""
import pytest
import os

from core.container import DependencyContainer
from core.app import bootstrap_container
from core.models import ToolRequestModel, ExecutionContextModel
from vision.models import VisionObservationModel, UIElementModel
from vision.vision_service import ScreenshotCaptureTool, _detect_ui_elements, _extract_ocr_text


def test_vision_observation_models():
    """Test Pydantic contract validation for VisionObservationModel and UIElementModel."""
    element = UIElementModel(
        element_type="button",
        label="Run Test",
        bounding_box={"x": 10, "y": 20, "w": 100, "h": 40}
    )
    obs = VisionObservationModel(
        ocr_text="Sample screen text",
        detected_elements=[element],
        focused_app="VS Code"
    )

    assert obs.focused_app == "VS Code"
    assert len(obs.detected_elements) == 1
    assert obs.detected_elements[0].label == "Run Test"
    assert obs.detected_elements[0].bounding_box["w"] == 100


def test_ui_element_detection_narrow():
    """Test targeted UI element detection for supported applications."""
    vscode_elements = _detect_ui_elements("VS Code")
    assert len(vscode_elements) >= 2
    labels = [e.label for e in vscode_elements]
    assert "Run & Debug" in labels

    chrome_elements = _detect_ui_elements("Chrome")
    assert len(chrome_elements) >= 2
    chrome_labels = [e.label for e in chrome_elements]
    assert "Address Bar" in chrome_labels


@pytest.mark.asyncio
async def test_screenshot_capture_tool_execution():
    """Test ScreenshotCaptureTool execution returning a typed VisionObservationModel dictionary."""
    tool = ScreenshotCaptureTool()
    req = ToolRequestModel(
        request_id="req_vision_1",
        correlation_id="cid_vision_1",
        capability="capture_screenshot",
        tool_name="screenshot_tool",
        args={"output_dir": "data/test_screenshots", "focused_app": "VS Code"}
    )

    res = await tool.execute(req)
    assert res.status == "completed"
    assert "ocr_text" in res.result
    assert "detected_elements" in res.result
    assert res.result["focused_app"] == "VS Code"


def test_execution_context_model_vision_integration():
    """Verify ExecutionContextModel integration with vision observations."""
    obs = VisionObservationModel(ocr_text="Main window title", focused_app="VS Code")
    ctx = ExecutionContextModel(
        focused_app="VS Code",
        vision_observation=obs.model_dump()
    )
    assert ctx.vision_observation is not None
    assert ctx.vision_observation["ocr_text"] == "Main window title"
