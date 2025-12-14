from __future__ import annotations

from typing import Dict, List, Set, Tuple

from src.lib.s3_storage.facade import (
    StorageControllerApi,
    StorageUpsert,
)
from src.lib.s4_solver.s40_grid_analyzer.grid_extractor import SolverFrontierView
from src.lib.s4_solver.facade import SolverAction, SolverActionType, SolverStats
from src.lib.s4_solver.s43_hybrid_solver import (
    HybridSolver,
    build_metadata_updates,
    compute_bounds,
)


class SolverController:
    """
    Façade minimale : charge le snapshot storage puis délègue à HybridSolver.
    Pas de logique métier ici (pipeline/CSP géré par HybridSolver).
    """

    def __init__(self, storage: StorageControllerApi):
        self._storage = storage
        self._stats = SolverStats(zones_analyzed=0, components_solved=0, safe_cells=0, flag_cells=0)
        self._solver = None

    def solve(self) -> List[SolverAction]:
        frontier_slice = self._storage.get_frontier()
        frontier_coords = set(frontier_slice.coords)
        if not frontier_coords:
            return []

        bounds = compute_bounds(frontier_coords)

        cells = self._storage.get_cells(bounds)
        view = SolverFrontierView(cells, frontier_coords)

        solver = HybridSolver(view, cells)
        solver.solve()
        self._solver = solver

        safe_cells = set(solver.get_safe_cells())
        flag_cells = set(solver.get_flag_cells())

        actions: List[SolverAction] = []
        actions.extend(
            SolverAction(cell=cell, type=SolverActionType.CLICK, confidence=1.0, reasoning="hybrid")
            for cell in safe_cells
        )
        actions.extend(
            SolverAction(cell=cell, type=SolverActionType.FLAG, confidence=1.0, reasoning="hybrid")
            for cell in flag_cells
        )

        if not actions:
            guess = solver.get_best_guess()
            if guess:
                x, y, prob = guess
                actions.append(
                    SolverAction(
                        cell=(x, y),
                        type=SolverActionType.GUESS,
                        confidence=1.0 - prob,
                        reasoning=f"CSP Best Guess ({prob*100:.1f}% mine)",
                    )
                )

        self._stats = SolverStats(
            zones_analyzed=len(solver.segmentation.zones) if solver.segmentation else 0,
            components_solved=len(solver.segmentation.components) if solver.segmentation else 0,
            safe_cells=len(safe_cells),
            flag_cells=len(flag_cells),
        )

        self._update_cell_metadata(cells, frontier_coords, safe_cells, flag_cells)
        return actions

    def _update_cell_metadata(
        self,
        cells: Dict[Tuple[int, int], "GridCell"],
        frontier_coords: Set[Tuple[int, int]],
        safe_cells: Set[Tuple[int, int]],
        flag_cells: Set[Tuple[int, int]],
    ) -> None:
        updated = build_metadata_updates(cells, frontier_coords, safe_cells, flag_cells)
        if updated:
            self._storage.upsert(StorageUpsert(cells=updated))

    def get_stats(self) -> SolverStats:
        return self._stats