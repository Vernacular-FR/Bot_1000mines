from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Protocol, Set, Tuple

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]


class CellState(str, Enum):
    """Possible states for a cell stored in s3."""

    UNKNOWN = "UNKNOWN"
    CLOSED = "CLOSED"
    OPEN_NUMBER = "OPEN_NUMBER"
    OPEN_EMPTY = "OPEN_EMPTY"
    FLAG = "FLAG"

    @property
    def is_revealed(self) -> bool:
        return self in {CellState.OPEN_NUMBER, CellState.OPEN_EMPTY}


class CellSource(str, Enum):
    """Origin of the latest information for a cell."""

    VISION = "VISION"
    SOLVER = "SOLVER"


class SolverStatus(str, Enum):
    """Lifecycle of a cell from the solver perspective."""

    UNRESOLVED = "UNRESOLVED"
    TO_PROCESS = "TO_PROCESS"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class GridCell:
    x: int
    y: int
    state: CellState
    value: Optional[int] = None  # 0..8 for numbers
    source: CellSource = CellSource.VISION
    solver_status: SolverStatus = SolverStatus.UNRESOLVED
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def coord(self) -> Coord:
        return (self.x, self.y)


@dataclass
class FrontierMetrics:
    size: int
    flag_density: float
    bbox: Optional[Bounds]
    pending_actions: int
    attractor_score: float


@dataclass
class FrontierSlice:
    coords: Set[Coord]
    metrics: FrontierMetrics


@dataclass
class StorageUpsert:
    cells: Dict[Coord, GridCell]
    revealed_add: Set[Coord] = field(default_factory=set)
    frontier_add: Set[Coord] = field(default_factory=set)
    frontier_remove: Set[Coord] = field(default_factory=set)


class StorageControllerApi(Protocol):
    def upsert(self, data: StorageUpsert) -> None: ...

    def get_frontier(self) -> FrontierSlice: ...

    def get_revealed(self) -> Set[Coord]: ...

    def mark_processed(self, positions: Set[Coord]) -> None: ...

    def get_cells(self, bounds: Bounds) -> Dict[Coord, GridCell]: ...

    def export_json(self, viewport_bounds: Bounds) -> Dict[str, object]: ...
