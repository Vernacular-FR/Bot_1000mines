"""Types pour le module s1_capture."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image

from src.lib.s0_coordinates.types import GridBounds, CanvasInfo


@dataclass
class CaptureInput:
    """Input pour la capture."""
    driver: Any  # WebDriver
    bounds: Optional[GridBounds] = None
    save_dir: Optional[str] = None
    game_id: Optional[str] = None


@dataclass
class CanvasCaptureResult:
    """Résultat brut d'une capture canvas."""
    image: Image.Image
    raw_bytes: bytes
    width: int
    height: int
    canvas_id: str
    saved_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CaptureResult:
    """Résultat complet de capture."""
    captures: List[CanvasCaptureResult]
    grid_bounds: Optional[GridBounds] = None
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def canvas_count(self) -> int:
        return len(self.captures)
    
    @property
    def composite_path(self) -> Optional[str]:
        return self.metadata.get("composite_path")
    
    @property
    def composite_bytes(self) -> Optional[bytes]:
        return self.metadata.get("composite_bytes")
    
    @property
    def composite_image(self) -> Optional[Image.Image]:
        """Reconstruit l'image composite à partir des bytes."""
        if self.composite_bytes:
            import io
            return Image.open(io.BytesIO(self.composite_bytes))
        return None
