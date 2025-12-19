"""Types pour le module s2_vision."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set

from src.lib.s0_coordinates.types import Coord, GridBounds


@dataclass
class CellMatch:
    """Résultat de reconnaissance d'une cellule."""
    coord: Coord
    symbol: str
    confidence: float
    distance: float = 0.0
    threshold: Optional[float] = None


@dataclass
class VisionInput:
    """Input pour l'analyse vision."""
    images: Dict[str, bytes]  # canvas_id -> image bytes
    bounds: GridBounds
    known_set: Optional[Set[Tuple[int, int]]] = None
    cell_size: int = 24


@dataclass
class VisionResult:
    """Résultat de l'analyse vision."""
    matches: List[CellMatch]
    timestamp: float = 0.0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def cell_count(self) -> int:
        return len(self.matches)
    
    def get_symbol_counts(self) -> Dict[str, int]:
        """Retourne le nombre de cellules par symbole."""
        counts: Dict[str, int] = {}
        for match in self.matches:
            counts[match.symbol] = counts.get(match.symbol, 0) + 1
        return counts
