"""Types pour le module s1_capture."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from PIL import Image


@dataclass
class CaptureInput:
    """Input pour une capture canvas."""
    canvas_id: str
    relative_origin: Tuple[float, float]  # (x, y) dans le canvas
    size: Tuple[int, int]  # (width, height)
    save: bool = False
    filename: Optional[str] = None
    bucket: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CaptureResult:
    """Résultat d'une capture canvas."""
    image: Image.Image
    raw_bytes: bytes
    width: int
    height: int
    timestamp: float = 0.0
    saved_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)
