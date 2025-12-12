from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Protocol, Set, Tuple

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]


class CellSource(str, Enum):
    """Origin of the latest information for a cell."""

    VISION = "VISION"
    SOLVER = "SOLVER"


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
    """Lifecycle of a cell from the solver perspective."""

    JUST_REVEALED = "JUST_REVEALED"
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
    LOOKUP = "LOOKUP"


@dataclass(frozen=True)
class GridCell:
    x: int
    y: int
    raw_state: RawCellState
    logical_state: LogicalCellState
    number_value: Optional[int] = None  # 1..8 for numbers
    source: CellSource = CellSource.VISION
    solver_status: SolverStatus = SolverStatus.NONE
    action_status: ActionStatus = ActionStatus.NONE
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def coord(self) -> Coord:
        return (self.x, self.y)


@dataclass
class FrontierSlice:
    coords: Set[Coord]


@dataclass
class StorageUpsert:
    cells: Dict[Coord, GridCell]
    revealed_add: Set[Coord] = field(default_factory=set)
    unresolved_add: Set[Coord] = field(default_factory=set)
    unresolved_remove: Set[Coord] = field(default_factory=set)
    frontier_add: Set[Coord] = field(default_factory=set)
    frontier_remove: Set[Coord] = field(default_factory=set)


class StorageControllerApi(Protocol):
    def upsert(self, data: StorageUpsert) -> None: ...
    def get_frontier(self) -> FrontierSlice: ...
    def get_revealed(self) -> Set[Coord]: ...
    def get_unresolved(self) -> Set[Coord]: ...
    def get_cells(self, bounds: Bounds) -> Dict[Coord, GridCell]: ...
    def export_json(self, viewport_bounds: Bounds) -> Dict[str, object]: ...
