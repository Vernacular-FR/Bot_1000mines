"""Module s1_capture : Capture des canvas."""

from .types import CaptureInput, CaptureResult, CanvasCaptureResult
from .capture import CanvasCaptureBackend, capture_canvas, capture_all_canvases

__all__ = [
    "CaptureInput",
    "CaptureResult",
    "CanvasCaptureResult",
    "CanvasCaptureBackend",
    "capture_canvas",
    "capture_all_canvases",
]
