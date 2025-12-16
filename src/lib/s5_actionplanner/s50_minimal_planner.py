from __future__ import annotations

from typing import List

from src.lib.s4_solver.facade import SolverAction, SolverActionType
from src.lib.s5_actionplanner.facade import PathfinderAction, PathfinderPlan


class MinimalPathfinder:
    """
    Implémentation minimale : tri flags -> clicks -> guesses, pas de déplacement viewport.
    """

    def plan_actions(self, actions: List[SolverAction]) -> PathfinderPlan:
        flags = [a for a in actions if a.type == SolverActionType.FLAG]
        clicks = [a for a in actions if a.type == SolverActionType.CLICK]
        guesses = [a for a in actions if a.type == SolverActionType.GUESS]

        ordered = flags + clicks + guesses

        pathfinder_actions = [
            PathfinderAction(
                type=a.type.value.lower(),
                cell=a.cell,
                confidence=a.confidence,
                reasoning=a.reasoning,
            )
            for a in ordered
        ]

        return PathfinderPlan(actions=pathfinder_actions, overlay_path=None)
