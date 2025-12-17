from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from src.lib.s3_storage.facade import StorageControllerApi
from src.lib.s4_solver.facade import SolverAction, SolverStats
from src.lib.s4_solver.s40_states_classifier.grid_extractor import SolverFrontierView
from src.lib.s4_solver.s49_optimized_solver import (
    OptimizedSolver,
    SolverUpdate,
    compute_bounds,
    compute_solver_update,
)

BYPASS_CSP_RATIO: float | None = None


class SolverController:
    """
    Façade minimale : charge le snapshot storage puis délègue à OptimizedSolver.
    Pas de logique métier ici (pipeline CSP géré par OptimizedSolver).
    """

    def __init__(self, storage: StorageControllerApi):
        self._storage = storage
        self._stats = SolverStats(zones_analyzed=0, components_solved=0, safe_cells=0, flag_cells=0)
        self._solver = None

    def solve(self) -> List[SolverAction]:
        """Compat: renvoie uniquement les actions solver (sans cleanup)."""
        update = self.solve_with_update()
        return update.actions if update else []

    def solve_with_update(self) -> Optional[SolverUpdate]:

        active_coords = set(self._storage.get_active())
        if not active_coords:
            return None

        bounds = compute_bounds(active_coords)
        cells = self._storage.get_cells(bounds)

        # Use frontier from storage instead of computing it
        frontier_coords = set(self._storage.get_frontier().coords)
        # Filter frontier within bounds
        x_min, y_min, x_max, y_max = bounds
        frontier_in_bounds = {
            (x, y)
            for (x, y) in frontier_coords
            if x_min <= x <= x_max and y_min <= y <= y_max
        }
        
        if not frontier_in_bounds:
            return None

        view = SolverFrontierView(cells, frontier_in_bounds)

        solver = OptimizedSolver(view, cells)
        solver.solve(bypass_ratio=BYPASS_CSP_RATIO)

        self._solver = solver

        update = self._build_update(cells, bounds, frontier_in_bounds, solver)
        self._stats = update.stats
        # Déclenche les overlays post-CSP (actions + cleanup) via le solver
        try:
            solver.emit_overlays((update.actions or []) + (update.cleanup_actions or []))
        except Exception:
            pass
        if (
            update.storage_upsert.cells
            or update.storage_upsert.active_remove
            or update.storage_upsert.frontier_add
            or update.storage_upsert.frontier_remove
            or update.storage_upsert.to_visualize
        ):
            self._storage.upsert(update.storage_upsert)
        return update

    def _build_update(
        self,
        cells: Dict[Tuple[int, int], "GridCell"],
        bounds: Tuple[int, int, int, int],
        frontier_coords: Set[Tuple[int, int]],
        solver: OptimizedSolver,
    ) -> SolverUpdate:
        current_frontier = set(self._storage.get_frontier().coords)
        x_min, y_min, x_max, y_max = bounds
        current_frontier_in_bounds = {
            (x, y)
            for (x, y) in current_frontier
            if x_min <= x <= x_max and y_min <= y <= y_max
        }
        return compute_solver_update(solver, cells, frontier_coords, current_frontier_in_bounds)

    def get_stats(self) -> SolverStats:
        return self._stats