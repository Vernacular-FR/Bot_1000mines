from __future__ import annotations

from typing import Dict, Any

from src.lib.s3_storage.controller import StorageController
from src.lib.s4_solver.controller import SolverController
from src.lib.s4_solver.facade import SolverAction, SolverStats
from src.lib.s5_actionplanner.s50_minimal_planner import MinimalPathfinder


class StorageSolverService:
    """
    Nouveau service s3 basé sur StorageController + SolverController.
    Remplace progressivement l'ancien service GridDB/tensor en rejouant uniquement le snapshot storage.
    """

    def __init__(self, storage: StorageController | None = None):
        self.storage = storage or StorageController()
        self.solver = SolverController(self.storage)
        self.pathfinder = MinimalPathfinder()

    def solve_snapshot(self) -> Dict[str, Any]:
        """
        Exécute le solver CSP sur l'état actuel de storage et retourne actions + stats.
        Overlays sont gérés côté solver via le contexte global (pas de préparation ici).
        """
        actions = self.solver.solve()
        stats = self.solver.get_stats()

        # Récupérer les artefacts internes pour le debug/overlays
        optimized_solver = getattr(self.solver, "_solver", None)
        segmentation = getattr(optimized_solver, "segmentation", None) if optimized_solver else None
        safe_cells = list(getattr(optimized_solver, "safe_cells", []) or [])
        flag_cells = list(getattr(optimized_solver, "flag_cells", []) or [])
        zone_probabilities = dict(getattr(optimized_solver, "zone_probabilities", {}) or {})
        reducer_safe = []
        reducer_flags = []
        if optimized_solver and getattr(optimized_solver, "csp_manager", None):
            reducer_result = getattr(optimized_solver.csp_manager, "reducer_result", None)
            if reducer_result:
                reducer_safe = list(getattr(reducer_result, "safe_cells", []) or [])
                reducer_flags = list(getattr(reducer_result, "flag_cells", []) or [])

        path_plan = self.pathfinder.plan_actions(actions)
        return {
            "success": True,
            "actions": actions,
            "stats": stats,
            "pathfinder_plan": path_plan,
            "segmentation": segmentation,
            "safe_cells": safe_cells,
            "flag_cells": flag_cells,
            "reducer_safe": reducer_safe,
            "reducer_flags": reducer_flags,
            "zone_probabilities": zone_probabilities,
        }

    def get_solver_actions(self) -> list[SolverAction]:
        return self.solver.solve()

    def get_solver_stats(self) -> SolverStats:
        return self.solver.get_stats()
