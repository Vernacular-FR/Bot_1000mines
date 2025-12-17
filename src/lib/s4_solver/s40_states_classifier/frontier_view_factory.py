from __future__ import annotations

from typing import Dict, Set

from ...s3_storage.controller import StorageController
from ...s3_storage.facade import Coord, FrontierRelevance
from .grid_extractor import SolverFrontierView


def build_frontier_view(storage: StorageController) -> SolverFrontierView:
    """
    Factory function to build a SolverFrontierView from storage snapshot.
    Uses frontier_set and frontier_to_process from storage.
    """
    # Get snapshot from storage
    cells = storage.get_cells()
    frontier_set = storage.get_frontier()
    
    # Filter frontier cells that need processing (TO_PROCESS)
    frontier_to_process: Set[Coord] = set()
    for coord in frontier_set:
        cell = cells.get(coord)
        if cell and cell.focus_level_frontier == FrontierRelevance.TO_PROCESS:
            frontier_to_process.add(coord)
    
    return SolverFrontierView(cells, frontier_to_process)
