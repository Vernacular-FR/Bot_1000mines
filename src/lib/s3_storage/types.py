"""Types et énumérations pour le storage et le solver."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]


class RawCellState(str, Enum):
    """État brut depuis la vision."""
    UNREVEALED = "unrevealed"
    EMPTY = "empty"
    NUMBER_1 = "number_1"
    NUMBER_2 = "number_2"
    NUMBER_3 = "number_3"
    NUMBER_4 = "number_4"
    NUMBER_5 = "number_5"
    NUMBER_6 = "number_6"
    NUMBER_7 = "number_7"
    NUMBER_8 = "number_8"
    FLAG = "flag"
    QUESTION = "question_mark"
    DECOR = "decor"
    EXPLODED = "exploded"


class CellState(str, Enum):
    """État normalisé pour le solver."""
    OPEN_NUMBER = "OPEN_NUMBER"
    CONFIRMED_MINE = "CONFIRMED_MINE"
    EMPTY = "EMPTY"
    UNREVEALED = "UNREVEALED"


class LogicalCellState(str, Enum):
    """État normalisé pour le solver."""
    OPEN_NUMBER = "OPEN_NUMBER"
    CONFIRMED_MINE = "CONFIRMED_MINE"
    EMPTY = "EMPTY"
    UNREVEALED = "UNREVEALED"


class SolverStatus(str, Enum):
    """Cycle de vie d'une cellule du point de vue du solver."""
    TO_VISUALIZE = "TO_VISUALIZE"
    JUST_VISUALIZED = "JUST_VISUALIZED"
    ACTIVE = "ACTIVE"
    FRONTIER = "FRONTIER"
    SOLVED = "SOLVED"
    MINE = "MINE"
    NONE = "NONE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ActionStatus(str, Enum):
    """Type d'action planifiée/appliquée."""
    NONE = "NONE"
    SAFE = "SAFE"
    FLAG = "FLAG"


class ActiveRelevance(str, Enum):
    """Focus level pour ACTIVE."""
    TO_REDUCE = "TO_REDUCE"
    REDUCED = "REDUCED"


class FrontierRelevance(str, Enum):
    """Focus level pour FRONTIER."""
    TO_PROCESS = "TO_PROCESS"
    PROCESSED = "PROCESSED"


@dataclass
class GridCell:
    """Représentation d'une cellule de la grille."""
    coord: Coord
    raw_state: RawCellState = RawCellState.UNREVEALED
    logical_state: LogicalCellState = LogicalCellState.UNREVEALED
    number_value: Optional[int] = None
    solver_status: SolverStatus = SolverStatus.NONE
    focus_level_active: ActiveRelevance = ActiveRelevance.TO_REDUCE
    focus_level_frontier: FrontierRelevance = FrontierRelevance.TO_PROCESS

    def __post_init__(self):
        """Support pour ancien constructeur avec x, y."""
        pass


class StorageUpsert:
    """Batch de mises à jour pour le storage."""
    
    def __init__(
        self,
        cells: Optional[Dict[Coord, GridCell]] = None,
        to_visualize: Optional[set] = None,
    ):
        self.cells = cells or {}
        self.to_visualize = to_visualize or set()
