from __future__ import annotations

from typing import List

from src.lib.s4_solver.facade import SolverAction
from src.lib.s5_actionplanner.facade import PathfinderPlan
from src.lib.s5_actionplanner.s50_minimal_planner import MinimalPathfinder


class ActionPlannerController:
    """
    Façade s5 : orchestre la planification minimale (tri flags/clicks/guesses).
    Pas de déplacement viewport dans cette version.
    """

    def __init__(self) -> None:
        self.pathfinder = MinimalPathfinder()

    def plan(self, actions: List[SolverAction]) -> PathfinderPlan:
        """
        Planifie les actions solver en ordre d’exécution (flags → clicks → guesses).
        """
        return self.pathfinder.plan_actions(actions)
