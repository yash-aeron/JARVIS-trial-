"""
vision/models.py — Strongly-typed Pydantic contracts for Vision & Desktop Understanding.
"""
import uuid
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class UIElementModel(BaseModel):
    """Represents a detected UI element (button, input, window) on screen."""
    element_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    element_type: str  # button | text_field | window | menu | icon
    label: str
    bounding_box: Dict[str, int] = Field(default_factory=dict)  # {"x": 100, "y": 200, "w": 150, "h": 40}
    is_clickable: bool = True
    confidence: float = 0.95


class VisionObservationModel(BaseModel):
    """Typed vision observation returned by screenshot capture, OCR, and element detection."""
    observation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=lambda: time.time())
    screen_resolution: str = "1920x1080"
    screenshot_path: Optional[str] = None
    ocr_text: str = ""
    detected_elements: List[UIElementModel] = Field(default_factory=list)
    active_window_title: str = ""
    focused_app: str = ""
