from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set, Tuple

from src.lib.s3_storage.facade import GridCell, LogicalCellState

Coord = Tuple[int, int]


@dataclass(frozen=True)
class FrontierClassification:
    active: Set[Coord]
    frontier: Set[Coord]
    solved: Set[Coord]
    unrevealed: Set[Coord]


class FrontierClassifier:
    """
    Étape 0 du solver : dérive les classes ACTIVE / FRONTIER / SOLVED
    à partir d'un snapshot brut de GridCell.
    """

    def __init__(self, cells: Dict[Coord, GridCell]):
        self._cells = cells

    def classify(self) -> FrontierClassification:
        active: Set[Coord] = set()
        solved: Set[Coord] = set()
        unrevealed: Set[Coord] = set()

        for coord, cell in self._cells.items():
            if cell.logical_state == LogicalCellState.OPEN_NUMBER and cell.number_value is not None:
                if self._has_unrevealed_neighbor(coord):
                    active.add(coord)
                else:
                    solved.add(coord)
            elif cell.logical_state in (LogicalCellState.EMPTY, LogicalCellState.CONFIRMED_MINE):
                solved.add(coord)
            elif cell.logical_state == LogicalCellState.UNREVEALED:
                unrevealed.add(coord)

        frontier: Set[Coord] = {
            coord for coord in unrevealed if self._has_active_neighbor(coord, active)
        }

        return FrontierClassification(
            active=active,
            frontier=frontier,
            solved=solved,
            unrevealed=unrevealed,
        )

    def _has_unrevealed_neighbor(self, coord: Coord) -> bool:
        for nb in self._neighbors(coord):
            neighbor = self._cells.get(nb)
            if neighbor and neighbor.logical_state == LogicalCellState.UNREVEALED:
                return True
        return False

    def _has_active_neighbor(self, coord: Coord, active_cells: Set[Coord]) -> bool:
        for nb in self._neighbors(coord):
            if nb in active_cells:
                return True
        return False

    @staticmethod
    def _neighbors(coord: Coord):
        x, y = coord
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                yield x + dx, y + dy
