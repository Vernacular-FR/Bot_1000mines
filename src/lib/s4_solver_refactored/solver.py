"""Solver principal : orchestration reducer + CSP."""

from typing import Dict, Set, Tuple, List, Optional, Any

from src.lib.s0_coordinates.types import Coord
from .types import (
    SolverInput, SolverOutput, SolverAction, ActionType,
    SolverStats, StorageUpsert, GridCell
)
from .reducer import FrontierReducer
from .csp import CspSolver


class Solver:
    """Orchestrateur principal du solver."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.max_csp_size = self.config.get("max_csp_size", 20)
        self.enable_guessing = self.config.get("enable_guessing", True)

    def solve(self, input: SolverInput) -> SolverOutput:
        """Résout le démineur et retourne les actions."""
        all_actions: List[SolverAction] = []
        stats = SolverStats(
            frontier_size=len(input.frontier),
            active_size=len(input.active_set),
        )

        # Phase 1: Réduction simple
        reducer = FrontierReducer(input.cells)
        reducer.reduce(input.frontier, input.active_set)
        reduction_actions = reducer.get_actions()
        all_actions.extend(reduction_actions)
        
        stats.safe_count = len(reducer.safe_cells)
        stats.flag_count = len(reducer.flag_cells)
        stats.reduction_passes = 1

        # Phase 2: CSP si pas assez d'actions
        excluded = reducer.safe_cells | reducer.flag_cells
        remaining_frontier = input.frontier - excluded
        
        if remaining_frontier and not all_actions:
            csp = CspSolver(input.cells, max_component_size=self.max_csp_size)
            csp.solve(input.frontier, input.active_set, excluded=excluded)
            csp_actions = csp.get_actions()
            all_actions.extend(csp_actions)
            
            stats.safe_count += len(csp.safe_cells)
            stats.flag_count += len(csp.flag_cells)

            # Phase 3: Guess si toujours pas d'actions
            if not all_actions and self.enable_guessing:
                guess = csp.get_best_guess()
                if guess:
                    all_actions.append(guess)
                    stats.guess_count = 1

        # Construction de l'upsert storage
        upsert = self._build_upsert(all_actions, input.cells)

        return SolverOutput(
            actions=all_actions,
            stats=stats,
            upsert=upsert,
            metadata={
                "frontier_size": len(input.frontier),
                "active_size": len(input.active_set),
            },
        )

    def _build_upsert(
        self,
        actions: List[SolverAction],
        cells: Dict[Tuple[int, int], GridCell],
    ) -> StorageUpsert:
        """Construit les mises à jour storage."""
        upsert = StorageUpsert()
        
        for action in actions:
            coord = action.to_tuple()
            update = {}
            
            if action.action == ActionType.CLICK:
                update["pending_click"] = True
            elif action.action == ActionType.FLAG:
                update["pending_flag"] = True
            elif action.action == ActionType.GUESS:
                update["pending_guess"] = True
                update["guess_probability"] = action.probability
            
            if update:
                upsert.cells_to_update[coord] = update
        
        return upsert


# === API fonctionnelle ===

_default_solver: Optional[Solver] = None


def _get_solver() -> Solver:
    global _default_solver
    if _default_solver is None:
        _default_solver = Solver()
    return _default_solver


def solve(input: SolverInput) -> SolverOutput:
    """Résout le démineur (API fonctionnelle)."""
    return _get_solver().solve(input)
