from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from src.lib.s3_storage.facade import (
    GridCell,
    Coord,
    LogicalCellState,
    RawCellState,
)

from src.lib.s4_solver.s43_csp_solver.csp_solver import GridAnalyzerProtocol
from src.lib.s4_solver.s43_csp_solver.segmentation import FrontierViewProtocol

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
            # Use logical_state for more precise filtering
            if cell.logical_state == LogicalCellState.OPEN_NUMBER and cell.number_value is not None:
                constraints.append((nx, ny))
        return constraints

    # --- GridAnalyzerProtocol -------------------------------------------------
    def get_cell(self, x: int, y: int) -> Optional[int]:
        cell = self._cells.get((x, y))
        if cell is None:
            return None
        if cell.logical_state == LogicalCellState.CONFIRMED_MINE:
            return self.FLAG
        if cell.logical_state in {LogicalCellState.OPEN_NUMBER, LogicalCellState.EMPTY}:
            return cell.number_value if cell.number_value is not None else 0
        if cell.raw_state in {RawCellState.UNREVEALED, RawCellState.QUESTION}:
            return self.UNKNOWN
        return None

    # --- Helpers --------------------------------------------------------------
    def _iter_neighbors(self, x: int, y: int):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                yield x + dx, y + dy
