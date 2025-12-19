"""Vue de la frontière pour le solver."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from src.lib.s3_storage.types import Coord, GridCell, LogicalCellState


class SolverFrontierView:
    """Vue adaptée de la grille pour le solver CSP."""

    FLAG = -1
    UNKNOWN = -2

    def __init__(self, cells: Dict[Coord, GridCell], frontier: Set[Coord]):
        self.cells = cells
        self.frontier = frontier
        self._neighbors_cache: Dict[Coord, List[Coord]] = {}

    def get_frontier_cells(self) -> Set[Coord]:
        return self.frontier

    def get_constraints_for_cell(self, x: int, y: int) -> List[Coord]:
        """Retourne les contraintes (cellules numérotées voisines)."""
        constraints = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                cell = self.cells.get((nx, ny))
                if cell and cell.logical_state == LogicalCellState.OPEN_NUMBER:
                    constraints.append((nx, ny))
        return constraints

    def get_cell(self, x: int, y: int) -> Optional[int]:
        """Retourne la valeur pour le CSP solver."""
        cell = self.cells.get((x, y))
        if cell is None:
            return None

        if cell.logical_state == LogicalCellState.CONFIRMED_MINE:
            return self.FLAG
        if cell.logical_state == LogicalCellState.UNREVEALED:
            return self.UNKNOWN
        if cell.logical_state == LogicalCellState.OPEN_NUMBER:
            return cell.number_value
        if cell.logical_state == LogicalCellState.EMPTY:
            return 0
        return None
