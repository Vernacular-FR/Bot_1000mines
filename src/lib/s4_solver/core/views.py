from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from src.lib.s3_storage.facade import CellState, GridCell, Coord

from .csp_solver import GridAnalyzerProtocol
from .segmentation import FrontierViewProtocol

Neighbor = Tuple[int, int]


class SolverFrontierView(FrontierViewProtocol, GridAnalyzerProtocol):
    """
    Vue statique sur la grille/ frontière pour le solver.
    Construit à partir d'un snapshot StorageController (frontier + cells).
    """

    FLAG = -2
    UNKNOWN = -1

    def __init__(self, cells: Dict[Coord, GridCell], frontier: Set[Coord]):
        self._cells = cells
        self._frontier = set(frontier)

    # --- FrontierViewProtocol -------------------------------------------------
    def get_frontier_cells(self) -> Set[Coord]:
        return self._frontier

    def get_constraints_for_cell(self, x: int, y: int) -> list[Neighbor]:
        constraints: list[Neighbor] = []
        for nx, ny in self._iter_neighbors(x, y):
            cell = self._cells.get((nx, ny))
            if not cell:
                continue
            if cell.state in {CellState.OPEN_NUMBER, CellState.OPEN_EMPTY} and cell.value is not None:
                constraints.append((nx, ny))
        return constraints

    # --- GridAnalyzerProtocol -------------------------------------------------
    def get_cell(self, x: int, y: int) -> Optional[int]:
        cell = self._cells.get((x, y))
        if cell is None:
            return None
        if cell.state == CellState.FLAG:
            return self.FLAG
        if cell.state in {CellState.OPEN_NUMBER, CellState.OPEN_EMPTY}:
            return cell.value if cell.value is not None else 0
        if cell.state == CellState.UNKNOWN or cell.state == CellState.CLOSED:
            return self.UNKNOWN
        return None

    # --- Helpers --------------------------------------------------------------
    def _iter_neighbors(self, x: int, y: int):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                yield x + dx, y + dy
