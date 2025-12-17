from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Protocol, Tuple

Coord = Tuple[int, int]


class SolverActionType(str, Enum):
    CLICK = "CLICK"
    FLAG = "FLAG"
    GUESS = "GUESS"


@dataclass
class SolverAction:
    cell: Coord
    type: SolverActionType
    confidence: float
    reasoning: str


@dataclass
class SolverStats:
    zones_analyzed: int
    components_solved: int
    safe_cells: int
    flag_cells: int


class SolverApi(Protocol):
    def solve(self, frontier_coords: List[Coord], active_coords: List[Coord]) -> List[SolverAction]:
        ...

    def get_stats(self) -> SolverStats:
        ...
