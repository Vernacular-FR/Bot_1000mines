from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Protocol, Set, Tuple

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]


class CellState(str, Enum):
    """Legacy state enum (derived from logical/raw data)."""

    UNKNOWN = "UNKNOWN"
    CLOSED = "CLOSED"
    OPEN_NUMBER = "OPEN_NUMBER"
    OPEN_EMPTY = "OPEN_EMPTY"
    FLAG = "FLAG"

    @property
    def is_revealed(self) -> bool:
        return self in {CellState.OPEN_NUMBER, CellState.OPEN_EMPTY}


class RawCellState(str, Enum):
    """Raw symbol classification straight from vision."""

    UNREVEALED = "UNREVEALED"
    NUMBER_1 = "NUMBER_1"
    NUMBER_2 = "NUMBER_2"
    NUMBER_3 = "NUMBER_3"
    NUMBER_4 = "NUMBER_4"
    NUMBER_5 = "NUMBER_5"
    NUMBER_6 = "NUMBER_6"
    NUMBER_7 = "NUMBER_7"
    NUMBER_8 = "NUMBER_8"
    FLAG = "FLAG"
    QUESTION = "QUESTION"
    EMPTY = "EMPTY"
    DECOR = "DECOR"
    EXPLODED = "EXPLODED"


class LogicalCellState(str, Enum):
    """Normalized state used by the solver."""

    OPEN_NUMBER = "OPEN_NUMBER"
    CONFIRMED_MINE = "CONFIRMED_MINE"
    EMPTY = "EMPTY"
    UNREVEALED = "UNREVEALED"


class SolverStatus(str, Enum):
    """Lifecycle of a cell from the solver perspective (topologie)."""

    TO_VISUALIZE = "TO_VISUALIZE"
    JUST_VISUALIZED = "JUST_VISUALIZED"
    ACTIVE = "ACTIVE"
    FRONTIER = "FRONTIER"
    SOLVED = "SOLVED"
    NONE = "NONE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ActionStatus(str, Enum):
    """Type of action planned/applied to this cell."""

    NONE = "NONE"
    SAFE = "SAFE"
    FLAG = "FLAG"


class ActiveRelevance(str, Enum):
    """FocusLevel pour ACTIVE."""

    TO_REDUCE = "TO_REDUCE"
    REDUCED = "REDUCED"


class FrontierRelevance(str, Enum):
    """FocusLevel pour FRONTIER."""

    TO_PROCESS = "TO_PROCESS"
    PROCESSED = "PROCESSED"


@dataclass(frozen=True)
class GridCell:
    x: int
    y: int
    raw_state: RawCellState
    logical_state: LogicalCellState
    number_value: Optional[int] = None  # 1..8 for numbers
    solver_status: SolverStatus = SolverStatus.NONE
    topological_state: SolverStatus = SolverStatus.NONE
    focus_level_active: Optional[ActiveRelevance] = None
    focus_level_frontier: Optional[FrontierRelevance] = None
    action_status: ActionStatus = ActionStatus.NONE
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def coord(self) -> Coord:
        return (self.x, self.y)

    @property
    def state(self) -> CellState:
        if self.logical_state == LogicalCellState.OPEN_NUMBER:
            return CellState.OPEN_NUMBER
        if self.logical_state == LogicalCellState.EMPTY:
            return CellState.OPEN_EMPTY
        if self.logical_state == LogicalCellState.CONFIRMED_MINE:
            return CellState.FLAG
        if self.raw_state == RawCellState.QUESTION:
            return CellState.UNKNOWN
        return CellState.CLOSED

    @property
    def value(self) -> Optional[int]:
        if self.logical_state == LogicalCellState.OPEN_NUMBER:
            return self.number_value
        if self.logical_state == LogicalCellState.EMPTY:
            return 0
        return None


@dataclass
class FrontierSlice:
    coords: Set[Coord]


@dataclass
class StorageUpsert:
    cells: Dict[Coord, GridCell]
    revealed_add: Set[Coord] = field(default_factory=set)
    active_add: Set[Coord] = field(default_factory=set)
    active_remove: Set[Coord] = field(default_factory=set)
    frontier_add: Set[Coord] = field(default_factory=set)
    frontier_remove: Set[Coord] = field(default_factory=set)
    to_visualize: Set[Coord] = field(default_factory=set)


class StorageControllerApi(Protocol):
    def upsert(self, data: StorageUpsert) -> None: ...
    def get_frontier(self) -> FrontierSlice: ...
    def get_revealed(self) -> Set[Coord]: ...
    def get_active(self) -> Set[Coord]: ...
    def get_cells(self, bounds: Bounds) -> Dict[Coord, GridCell]: ...
    def export_json(self, viewport_bounds: Bounds) -> Dict[str, object]: ...
