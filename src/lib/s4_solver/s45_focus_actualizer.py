from __future__ import annotations

from dataclasses import replace
from typing import Dict, Set

from ..s3_storage.facade import (
    ActiveRelevance,
    Coord,
    FrontierRelevance,
    GridCell,
    SolverStatus,
    StorageUpsert,
)


class FocusActualizer:
    """Stateless module for managing focus level promotions."""

    @staticmethod
    def promote_focus(cells: Dict[Coord, GridCell]) -> StorageUpsert:
        """
        Promote focus levels based on solver context.
        Returns a StorageUpsert with updated focus levels.
        """
        updated_cells: Dict[Coord, GridCell] = {}
        
        for coord, cell in cells.items():
            new_cell = cell
            
            # Promote REDUCED -> TO_REDUCE for ACTIVE cells
            if cell.solver_status == SolverStatus.ACTIVE:
                if cell.focus_level_active == ActiveRelevance.REDUCED:
                    new_cell = replace(cell, focus_level_active=ActiveRelevance.TO_REDUCE)
            
            # Promote PROCESSED -> TO_PROCESS for FRONTIER cells
            elif cell.solver_status == SolverStatus.FRONTIER:
                if cell.focus_level_frontier == FrontierRelevance.PROCESSED:
                    new_cell = replace(cell, focus_level_frontier=FrontierRelevance.TO_PROCESS)
            
            if new_cell != cell:
                updated_cells[coord] = new_cell
        
        return StorageUpsert(
            cells=updated_cells,
            revealed_add=set(),
            active_add=set(),
            active_remove=set(),
            frontier_add=set(),
            frontier_remove=set(),
            to_visualize=set(),
        )
