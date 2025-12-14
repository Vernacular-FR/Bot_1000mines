from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from src.lib.s3_storage.facade import GridCell, LogicalCellState

Coord = Tuple[int, int]


@dataclass
class ConstraintReducerResult:
    safe_cells: Set[Coord]
    flag_cells: Set[Coord]


class ConstraintReducer:
    """Déduce les cellules sûres / mines 100% déterminées par les chiffres existants."""

    def __init__(self, cells: Dict[Coord, GridCell]):
        self.cells = cells

    def reduce(self) -> ConstraintReducerResult:
        safe_cells: Set[Coord] = set()
        flag_cells: Set[Coord] = set()

        numbered = {
            coord for coord, cell in self.cells.items()
            if cell.logical_state == LogicalCellState.OPEN_NUMBER and cell.number_value is not None
        }
        queue: List[Coord] = list(numbered)
        processed: Set[Coord] = set()

        while queue:
            coord = queue.pop()
            if coord in processed:
                continue

            cell = self.cells.get(coord)
            if not cell or cell.logical_state != LogicalCellState.OPEN_NUMBER or cell.number_value is None:
                continue

            closed_neighbors, flagged_count = self._classify_neighbors(coord, flag_cells)
            remaining = cell.number_value - flagged_count

            if remaining < 0:
                processed.add(coord)
                continue

            updated = False
            if remaining == 0 and closed_neighbors:
                for nb in closed_neighbors:
                    if nb not in safe_cells:
                        safe_cells.add(nb)
                        queue.extend(self._number_neighbors(nb))
                updated = True

            elif remaining == len(closed_neighbors) and closed_neighbors:
                for nb in closed_neighbors:
                    if nb not in flag_cells:
                        flag_cells.add(nb)
                        queue.extend(self._number_neighbors(nb))
                updated = True

            if updated:
                # Re-évaluer ce chiffre et ses voisins avec les nouvelles infos.
                queue.extend(self._number_neighbors(coord))
            else:
                processed.add(coord)

        return ConstraintReducerResult(safe_cells=safe_cells, flag_cells=flag_cells)

    def _classify_neighbors(
        self, coord: Coord, inferred_flags: Set[Coord]
    ) -> Tuple[List[Coord], int]:
        closed: List[Coord] = []
        flagged = 0

        for nb in self._neighbors(coord):
            cell = self.cells.get(nb)
            if not cell:
                continue
            if cell.logical_state == LogicalCellState.CONFIRMED_MINE or nb in inferred_flags:
                flagged += 1
            elif cell.logical_state == LogicalCellState.UNREVEALED:
                closed.append(nb)

        return closed, flagged

    def _number_neighbors(self, coord: Coord) -> List[Coord]:
        numbers: List[Coord] = []
        for nb in self._neighbors(coord):
            cell = self.cells.get(nb)
            if cell and cell.logical_state == LogicalCellState.OPEN_NUMBER and cell.number_value is not None:
                numbers.append(nb)
        return numbers

    def _neighbors(self, coord: Coord) -> List[Coord]:
        x, y = coord
        return [
            (x + dx, y + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if not (dx == 0 and dy == 0)
        ]
