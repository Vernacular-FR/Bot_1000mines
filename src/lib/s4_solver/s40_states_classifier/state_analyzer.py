from __future__ import annotations

from dataclasses import replace
from typing import Dict, Set, Tuple

from ...s3_storage.facade import (
    ActiveRelevance,
    Coord,
    FrontierRelevance,
    GridCell,
    LogicalCellState,
    SolverStatus,
    StorageUpsert,
)
from ..s45_focus_actualizer import FocusActualizer
from .grid_classifier import FrontierClassifier


class StateAnalyzer:
    """
    State analyzer with focus actualization.
    Performs topological classification and triggers focus promotions.
    """

    def __init__(self):
        self.focus_actualizer = FocusActualizer()

    def analyze_and_promote(self, cells: Dict[Coord, GridCell]) -> StorageUpsert:
        """
        Analyze cells for topological classification and promote focus levels.
        Returns a StorageUpsert with updated solver_status and focus levels.
        """
        # Step 1: Topological classification
        classifier = FrontierClassifier(cells)
        classification = classifier.classify()
        
        # Step 2: Create updated cells with new solver_status
        updated_cells: Dict[Coord, GridCell] = {}
        
        # Update ACTIVE cells
        for coord in classification.active:
            cell = cells[coord]
            if cell.solver_status != SolverStatus.ACTIVE:
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.ACTIVE,
                    topological_state=SolverStatus.ACTIVE,
                    focus_level_active=ActiveRelevance.TO_REDUCE,
                    focus_level_frontier=None
                )
        
        # Update FRONTIER cells
        for coord in classification.frontier:
            cell = cells[coord]
            if cell.solver_status != SolverStatus.FRONTIER:
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.FRONTIER,
                    topological_state=SolverStatus.FRONTIER,
                    focus_level_active=None,
                    focus_level_frontier=FrontierRelevance.TO_PROCESS
                )
        
        # Update SOLVED cells
        for coord in classification.solved:
            cell = cells[coord]
            if cell.solver_status != SolverStatus.SOLVED:
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.SOLVED,
                    topological_state=SolverStatus.SOLVED,
                    focus_level_active=None,
                    focus_level_frontier=None
                )
        
        # Step 3: Apply focus promotions to updated cells
        if updated_cells:
            focus_upsert = self.focus_actualizer.promote_focus(updated_cells)
            # Merge focus updates with our status updates
            updated_cells.update(focus_upsert.cells)
        
        return StorageUpsert(
            cells=updated_cells,
            revealed_add=set(),
            active_add=classification.active,
            active_remove=set(),
            frontier_add=classification.frontier,
            frontier_remove=set(),
            to_visualize=set(),
        )
