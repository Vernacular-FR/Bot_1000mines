"""Module s1_capture : Capture canvas."""

from .capture import capture_canvas, capture_zone, CanvasCaptureBackend
from .types import CaptureInput, CaptureResult

__all__ = [
    "capture_canvas",
    "capture_zone",
    "CanvasCaptureBackend",
    "CaptureInput",
    "CaptureResult",
]
