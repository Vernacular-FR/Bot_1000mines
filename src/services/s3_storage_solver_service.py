from __future__ import annotations

from typing import Dict, Any

from src.lib.s3_storage.controller import StorageController
from src.lib.s4_solver.controller import SolverController
from src.lib.s4_solver.facade import SolverAction, SolverStats


class StorageSolverService:
    """
    Nouveau service s3 basé sur StorageController + SolverController.
    Remplace progressivement l'ancien service GridDB/tensor en rejouant uniquement le snapshot storage.
    """

    def __init__(self, storage: StorageController | None = None):
        self.storage = storage or StorageController()
        self.solver = SolverController(self.storage)

    def solve_snapshot(self) -> Dict[str, Any]:
        """
        Exécute le solver CSP sur l'état actuel de storage et retourne actions + stats.
        """
        actions = self.solver.solve()
        stats = self.solver.get_stats()
        return {
            "success": True,
            "actions": actions,
            "stats": stats,
        }

    def get_solver_actions(self) -> list[SolverAction]:
        return self.solver.solve()

    def get_solver_stats(self) -> SolverStats:
        return self.solver.get_stats()
