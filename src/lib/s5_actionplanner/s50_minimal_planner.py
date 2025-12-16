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
        # On ignore les guesses à ce stade (le solver peut en émettre, mais s5 ne les exécute pas)
        # guesses = [a for a in actions if a.type == SolverActionType.GUESS]

        # Ordre : flags -> (double) clicks -> guesses
        pathfinder_actions: list[PathfinderAction] = []

        for a in flags:
            pathfinder_actions.append(
                PathfinderAction(
                    type=a.type.value.lower(),
                    cell=a.cell,
                    confidence=a.confidence,
                    reasoning=a.reasoning,
                )
            )

        # Double clic logique : on injecte deux actions click successives sur chaque safe
        for a in clicks:
            click_payload = {
                "type": a.type.value.lower(),
                "cell": a.cell,
                "confidence": a.confidence,
                "reasoning": a.reasoning,
            }
            pathfinder_actions.append(PathfinderAction(**click_payload))
            pathfinder_actions.append(PathfinderAction(**click_payload))

        return PathfinderPlan(actions=pathfinder_actions, overlay_path=None)
