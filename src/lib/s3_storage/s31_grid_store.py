from __future__ import annotations

from typing import Dict, Set, Tuple

from .facade import (
    ActiveRelevance,
    Bounds,
    Coord,
    FrontierRelevance,
    GridCell,
    LogicalCellState,
    SolverStatus,
    StorageUpsert,
)
from .s32_set_manager import SetManager


class GridStore:
    """Sparse grid storage with delegated set management."""

    def __init__(self) -> None:
        self._cells: Dict[Coord, GridCell] = {}
        self._sets = SetManager()

    def apply_upsert(self, data: StorageUpsert) -> None:
        """Apply batch updates to grid and sets."""
        self._validate_cells(data.cells)
        
        # Update cells first
        self._cells.update(data.cells)
        
        # Then recalculate sets based on updated cells
        self._recalculate_sets(data.cells)
        
        # Apply explicit to_visualize additions (solver-only)
        if data.to_visualize:
            self._sets.apply_set_updates(
                revealed_add=set(),
                active_add=set(),
                active_remove=set(),
                frontier_add=set(),
                frontier_remove=set(),
                to_visualize=data.to_visualize,
            )

    def get_frontier_slice(self) -> Set[Coord]:
        """Return frontier coordinates."""
        return self._sets.get_frontier()

    def get_revealed(self) -> Set[Coord]:
        """Return revealed coordinates."""
        return self._sets.get_revealed()

    def get_active(self) -> Set[Coord]:
        """Return active coordinates."""
        return self._sets.get_active()

    def get_to_visualize(self) -> Set[Coord]:
        """Return coordinates flagged for re-capture."""
        return self._sets.get_to_visualize()

    def get_cells_in_bounds(self, bounds: Bounds) -> Dict[Coord, GridCell]:
        """Extract cells within rectangular bounds."""
        x_min, y_min, x_max, y_max = bounds
        result = {}
        for coord, cell in self._cells.items():
            x, y = coord
            if x_min <= x <= x_max and y_min <= y <= y_max:
                result[coord] = cell
        return result

    def iter_frontier_in_bounds(self, bounds: Bounds) -> Set[Coord]:
        """Iterate frontier coordinates within bounds."""
        x_min, y_min, x_max, y_max = bounds
        result = set()
        for coord, cell in self._cells.items():
            x, y = coord
            if x_min <= x <= x_max and y_min <= y <= y_max:
                result.add(coord)
        return result

    # ------------------------------------------------------------------ #
    # Internal validation helpers                                        #
    # ------------------------------------------------------------------ #
    def _recalculate_sets(self, modified_cells: Dict[Coord, GridCell]) -> None:
        """Recalculate sets incrementally based on modified cells."""
        # Remove modified coords from all sets first
        for coord in modified_cells:
            self._sets.remove_from_all_sets(coord)
        
        # Add coords to appropriate sets based on new solver_status
        for coord, cell in modified_cells.items():
            if cell.solver_status == SolverStatus.ACTIVE:
                self._sets.add_to_active(coord)
            elif cell.solver_status == SolverStatus.FRONTIER:
                self._sets.add_to_frontier(coord)
            
            # Add to known_set if solver_status is not NONE
            if cell.solver_status != SolverStatus.NONE:
                self._sets.add_to_known(coord)
            
            # Add to revealed_set for OPEN_NUMBER or EMPTY
            if cell.logical_state in (LogicalCellState.OPEN_NUMBER, LogicalCellState.EMPTY):
                self._sets.add_to_revealed(coord)

    def _validate_cells(self, cells: Dict[Coord, GridCell]) -> None:
        """
        Enforce consistency between solver_status and focus levels:
        - ACTIVE -> focus_level_active in {TO_REDUCE, REDUCED}, focus_level_frontier is None
        - FRONTIER -> focus_level_frontier in {TO_PROCESS, PROCESSED}, focus_level_active is None
        - Others -> both focus levels must be None
        """
        for coord, cell in cells.items():
            if cell.solver_status == SolverStatus.ACTIVE:
                if cell.focus_level_active not in {ActiveRelevance.TO_REDUCE, ActiveRelevance.REDUCED}:
                    raise ValueError(
                        f"Incohérence focus ACTIVE pour {coord}: {cell.focus_level_active}"
                    )
                if cell.focus_level_frontier is not None:
                    raise ValueError(
                        f"focus_level_frontier doit être None pour ACTIVE ({coord})"
                    )
            elif cell.solver_status == SolverStatus.FRONTIER:
                if cell.focus_level_frontier not in {
                    FrontierRelevance.TO_PROCESS,
                    FrontierRelevance.PROCESSED,
                }:
                    raise ValueError(
                        f"Incohérence focus FRONTIER pour {coord}: {cell.focus_level_frontier}"
                    )
                if cell.focus_level_active is not None:
                    raise ValueError(
                        f"focus_level_active doit être None pour FRONTIER ({coord})"
                    )
            else:
                if cell.focus_level_active is not None or cell.focus_level_frontier is not None:
                    raise ValueError(
                        f"focus levels doivent être None hors ACTIVE/FRONTIER ({coord})"
                    )
            # Coherence logique_state / number_value
            if cell.logical_state == LogicalCellState.OPEN_NUMBER:
                if cell.number_value is None:
                    raise ValueError(f"number_value manquant pour OPEN_NUMBER ({coord})")
            else:
                if cell.number_value is not None:
                    raise ValueError(f"number_value doit être None hors OPEN_NUMBER ({coord})")
