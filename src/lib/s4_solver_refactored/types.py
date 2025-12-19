"""Types pour le module s4_solver."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Set, Tuple, Optional, Any

from src.lib.s0_coordinates.types import Coord


class ActionType(Enum):
    """Type d'action solver."""
    CLICK = auto()
    FLAG = auto()
    GUESS = auto()


@dataclass
class SolverAction:
    """Action proposée par le solver."""
    coord: Coord
    action: ActionType
    confidence: float = 1.0
    probability: float = 0.0  # Probabilité d'être une mine (pour GUESS)
    
    def to_tuple(self) -> Tuple[int, int]:
        return (self.coord.row, self.coord.col)


@dataclass
class SolverStats:
    """Statistiques de résolution."""
    safe_count: int = 0
    flag_count: int = 0
    guess_count: int = 0
    frontier_size: int = 0
    active_size: int = 0
    csp_components: int = 0
    reduction_passes: int = 0
    
    @property
    def total_actions(self) -> int:
        return self.safe_count + self.flag_count + self.guess_count


@dataclass
class GridCell:
    """Cellule de grille pour le solver."""
    coord: Coord
    value: int  # -1=unrevealed, 0=empty, 1-8=number, -2=flag, -3=exploded
    is_revealed: bool = False
    is_flagged: bool = False
    
    @property
    def is_number(self) -> bool:
        return 1 <= self.value <= 8
    
    @property
    def adjacent_mine_count(self) -> int:
        return self.value if self.is_number else 0


@dataclass
class SolverInput:
    """Input pour le solver."""
    cells: Dict[Tuple[int, int], GridCell]
    frontier: Set[Tuple[int, int]]  # Cellules unrevealed adjacentes à des nombres
    active_set: Set[Tuple[int, int]]  # Cellules nombres avec contraintes actives
    config: Optional[Dict[str, Any]] = None


@dataclass
class StorageUpsert:
    """Mises à jour à appliquer au storage."""
    cells_to_update: Dict[Tuple[int, int], Dict[str, Any]] = field(default_factory=dict)
    frontier_updates: Set[Tuple[int, int]] = field(default_factory=set)
    active_updates: Set[Tuple[int, int]] = field(default_factory=set)


@dataclass
class SolverOutput:
    """Output du solver."""
    actions: List[SolverAction]
    stats: SolverStats
    upsert: StorageUpsert
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_actions(self) -> bool:
        return len(self.actions) > 0
    
    @property
    def safe_actions(self) -> List[SolverAction]:
        return [a for a in self.actions if a.action == ActionType.CLICK]
    
    @property
    def flag_actions(self) -> List[SolverAction]:
        return [a for a in self.actions if a.action == ActionType.FLAG]
    
    @property
    def guess_actions(self) -> List[SolverAction]:
        return [a for a in self.actions if a.action == ActionType.GUESS]
