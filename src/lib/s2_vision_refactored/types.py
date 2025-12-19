"""Types pour le module s2_vision."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from PIL import Image

from src.lib.s0_coordinates.types import Coord, GridBounds


# === Symboles reconnus ===

SYMBOL_TO_VALUE = {
    "empty": 0,
    "number_1": 1,
    "number_2": 2,
    "number_3": 3,
    "number_4": 4,
    "number_5": 5,
    "number_6": 6,
    "number_7": 7,
    "number_8": 8,
    "unrevealed": -1,
    "flag": -2,
    "exploded": -3,
    "question_mark": -4,
    "decor": -5,
    "unknown": -99,
}

VALUE_TO_SYMBOL = {v: k for k, v in SYMBOL_TO_VALUE.items()}


@dataclass
class MatchResult:
    """Résultat de classification d'une cellule."""
    symbol: str
    distance: float
    threshold: Optional[float]
    distances: Dict[str, float]
    margin: int

    @property
    def confidence(self) -> float:
        if not self.threshold or self.threshold <= 0:
            return 0.0
        return max(0.0, 1.0 - (self.distance / (self.threshold + 1e-6)))

    @property
    def value(self) -> int:
        return SYMBOL_TO_VALUE.get(self.symbol, -99)


@dataclass
class CellMatch:
    """Match d'une cellule avec ses coordonnées."""
    coord: Coord
    symbol: str
    value: int
    confidence: float
    distance: float = 0.0

    @classmethod
    def from_match_result(cls, coord: Coord, result: MatchResult) -> "CellMatch":
        return cls(
            coord=coord,
            symbol=result.symbol,
            value=result.value,
            confidence=result.confidence,
            distance=result.distance,
        )


@dataclass
class VisionInput:
    """Input pour l'analyse vision."""
    image: Image.Image
    bounds: GridBounds
    known_coords: Optional[set] = None  # Coordonnées déjà connues (à ignorer)
    allowed_symbols: Optional[Tuple[str, ...]] = None


@dataclass
class VisionResult:
    """Résultat de l'analyse vision."""
    matches: List[CellMatch]
    bounds: GridBounds
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def match_count(self) -> int:
        return len(self.matches)

    def get_matches_by_symbol(self, symbol: str) -> List[CellMatch]:
        return [m for m in self.matches if m.symbol == symbol]

    def to_dict(self) -> Dict[Tuple[int, int], CellMatch]:
        return {(m.coord.row, m.coord.col): m for m in self.matches}
