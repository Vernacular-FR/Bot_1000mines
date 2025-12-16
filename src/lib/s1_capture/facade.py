from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Tuple

from PIL import Image

from src.lib.s0_interface.facade import InterfaceControllerApi


@dataclass
class CaptureRequest:
    """Représente une demande de capture depuis le CanvasSpace du jeu."""

    canvas_point: Tuple[float, float]
    size: Tuple[int, int]
    save: bool = False
    filename: Optional[str] = None
    bucket: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CaptureResult:
    """Résultat consolidé d'une capture."""

    image: Image.Image
    raw_bytes: bytes
    width: int
    height: int
    saved_path: Optional[str]
    metadata: Optional[Dict[str, Any]] = None


class CaptureControllerApi(Protocol):
    def capture_zone(self, request: CaptureRequest) -> CaptureResult: ...

    def capture_grid_window(
        self,
        grid_bounds: Tuple[int, int, int, int],
        *,
        save: bool = False,
        annotate: bool = False,
        filename: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> CaptureResult: ...


__all__ = [
    "CaptureRequest",
    "CaptureResult",
    "CaptureControllerApi",
    "InterfaceControllerApi",
]
