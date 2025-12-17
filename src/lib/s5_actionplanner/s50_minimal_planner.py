from __future__ import annotations

from typing import List

from src.lib.s4_solver.facade import SolverAction, SolverActionType
from src.lib.s5_actionplanner.facade import PathfinderAction, PathfinderPlan


class MinimalPathfinder:
    """
    Implémentation minimale : tri flags -> clicks -> guesses, pas de déplacement viewport.
    Ajoute un double-clic sur les SAFE et un ménage local optionnel autour des SAFE.
    """

    def __init__(self, enable_local_cleanup: bool = False) -> None:
        self.enable_local_cleanup = enable_local_cleanup

    def plan_actions(self, actions: List[SolverAction]) -> PathfinderPlan:
        flags = [a for a in actions if a.type == SolverActionType.FLAG]
        clicks = [a for a in actions if a.type == SolverActionType.CLICK]
        # On ignore les guesses à ce stade (le solver peut en émettre, mais s5 ne les exécute pas)

        # Ordre : flags -> double_click (SAFE) -> clicks cleanup -> guesses (ignorés ici)
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

        # SAFE : double-clic natif sur les CLICK non-cleanup
        safe_cells = {a.cell for a in clicks if "cleanup" not in (a.reasoning or "")}
        for cell in safe_cells:
            # on prend la première action correspondante pour confidence/reasoning
            ref = next(a for a in clicks if a.cell == cell and "cleanup" not in (a.reasoning or ""))
            payload = {
                "type": "double_click",
                "cell": cell,
                "confidence": ref.confidence,
                "reasoning": ref.reasoning,
            }
            pathfinder_actions.append(PathfinderAction(**payload))

        # CLEANUP : un seul clic par cellule (raisoning contenant "cleanup")
        cleanup_cells = {a.cell for a in clicks if "cleanup" in (a.reasoning or "")}
        for cell in cleanup_cells:
            ref = next(a for a in clicks if a.cell == cell and "cleanup" in (a.reasoning or ""))
            pathfinder_actions.append(
                PathfinderAction(
                    type="click",
                    cell=cell,
                    confidence=ref.confidence,
                    reasoning=ref.reasoning,
                )
            )

        # Flags : dédup (cell, type)
        dedup: list[PathfinderAction] = []
        seen: set[tuple[tuple[int, int], str]] = set()
        for pa in pathfinder_actions:
            key = (pa.cell, pa.type)
            if key in seen:
                continue
            seen.add(key)
            dedup.append(pa)

        return PathfinderPlan(actions=dedup, overlay_path=None)
