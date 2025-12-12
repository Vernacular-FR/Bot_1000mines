from __future__ import annotations

from typing import List, Tuple

from src.lib.s3_storage.facade import Bounds, StorageControllerApi
from src.lib.s4_solver.core import SolverFrontierView, Segmentation
from src.lib.s4_solver.facade import SolverAction, SolverActionType, SolverStats
from src.lib.s4_solver.hybrid_solver import HybridSolver


class SolverController:
    """
    Minimal solver orchestrating Segmentation + CSP from storage snapshot.
    PatternEngine viendra plus tard (phase 2).
    """

    def __init__(self, storage: StorageControllerApi):
        self._storage = storage
        self._stats = SolverStats(zones_analyzed=0, components_solved=0, safe_cells=0, flag_cells=0)
        self._solver = None  # Initialize solver attribute

    def solve(self) -> List[SolverAction]:
        """Résout la grille actuelle et retourne les actions suggérées."""
        # Obtenir les données du storage avec l'API correcte
        frontier_slice = self._storage.get_frontier()
        frontier_coords = set(frontier_slice.coords)
        
        # Calculer les bornes pour obtenir les cellules nécessaires
        if not frontier_coords:
            return []
        
        xs = [x for x, _ in frontier_coords]
        ys = [y for _, y in frontier_coords]
        min_x, max_x = min(xs) - 2, max(xs) + 3
        min_y, max_y = min(ys) - 2, max(ys) + 3
        bounds = (min_x, min_y, max_x, max_y)
        
        cells = self._storage.get_cells(bounds)
        view = SolverFrontierView(cells, frontier_coords)
        
        # Utiliser HybridSolver pour résoudre
        solver = HybridSolver(view, cells)
        solver.solve()
        self._solver = solver  # Store for access to segmentation
        
        safe_cells = solver.get_safe_cells()
        flag_cells = solver.get_flag_cells()
        
        actions: List[SolverAction] = []
        actions.extend(
            SolverAction(cell=cell, type=SolverActionType.CLICK, confidence=1.0, reasoning="CSP (0% mine)")
            for cell in safe_cells
        )
        actions.extend(
            SolverAction(cell=cell, type=SolverActionType.FLAG, confidence=1.0, reasoning="CSP (100% mine)")
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
        
        # Mettre à jour les stats
        self._stats = SolverStats(
            zones_analyzed=len(solver.segmentation.zones),
            components_solved=len(solver.segmentation.components),
            safe_cells=len(safe_cells),
            flag_cells=len(flag_cells)
        )
        
        return actions

    def get_stats(self) -> SolverStats:
        return self._stats

    def _compute_bounds(self, coords: List[Tuple[int, int]]) -> Bounds:
        xs = [x for x, _ in coords]
        ys = [y for _, y in coords]
        min_x, max_x = min(xs) - 2, max(xs) + 3
        min_y, max_y = min(ys) - 2, max(ys) + 3
        return (min_x, min_y, max_x, max_y)