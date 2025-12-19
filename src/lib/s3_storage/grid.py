"""Stockage sparse de la grille."""

from __future__ import annotations

from typing import Dict, Set, Tuple

from .types import (
    Bounds,
    Coord,
    GridCell,
    LogicalCellState,
    SolverStatus,
    StorageUpsert,
)
from .sets import SetManager


class GridStore:
    """Stockage sparse de la grille avec gestion des ensembles."""

    def __init__(self) -> None:
        self._cells: Dict[Coord, GridCell] = {}
        self._sets = SetManager()

    def apply_upsert(self, data: StorageUpsert) -> None:
        """Applique les mises à jour en batch."""
        self._cells.update(data.cells)
        self._recalculate_sets(data.cells)
        
        if data.to_visualize:
            self._sets.apply_set_updates(
                revealed_add=set(),
                active_add=set(),
                active_remove=set(),
                frontier_add=set(),
                frontier_remove=set(),
                to_visualize=data.to_visualize,
            )

    def get_frontier(self) -> Set[Coord]:
        return self._sets.get_frontier()

    def get_revealed(self) -> Set[Coord]:
        return self._sets.get_revealed()

    def get_active(self) -> Set[Coord]:
        return self._sets.get_active()

    def get_to_visualize(self) -> Set[Coord]:
        return self._sets.get_to_visualize()

    def get_known(self) -> Set[Coord]:
        return self._sets.get_known()

    def get_cells_in_bounds(self, bounds: Bounds) -> Dict[Coord, GridCell]:
        """Retourne les cellules dans les bornes."""
        x_min, y_min, x_max, y_max = bounds
        return {
            coord: cell
            for coord, cell in self._cells.items()
            if x_min <= coord[0] <= x_max and y_min <= coord[1] <= y_max
        }

    def get_all_cells(self) -> Dict[Coord, GridCell]:
        """Retourne toutes les cellules."""
        return dict(self._cells)

    def _recalculate_sets(self, modified_cells: Dict[Coord, GridCell]) -> None:
        """Recalcule les ensembles basés sur les cellules modifiées.
        
        Ajoute à known_set seulement les cellules NON UNREVEALED.
        Une cellule UNREVEALED ne doit jamais être dans known_set, même si visualisée.
        """
        for coord in modified_cells:
            self._sets.remove_from_state_sets(coord)
        
        for coord, cell in modified_cells.items():
            # Ajouter à known_set seulement si logical_state != UNREVEALED
            # Règle : seules les cellules révélées (non unrevealed) sont "connues"
            if cell.logical_state != LogicalCellState.UNREVEALED:
                self._sets.add_to_known(coord)
            
            if cell.logical_state in {LogicalCellState.OPEN_NUMBER, LogicalCellState.EMPTY}:
                self._sets.add_to_revealed(coord)
            
            if cell.solver_status == SolverStatus.ACTIVE:
                self._sets.add_to_active(coord)
            elif cell.solver_status == SolverStatus.FRONTIER:
                self._sets.add_to_frontier(coord)
