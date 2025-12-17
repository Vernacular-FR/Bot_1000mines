from __future__ import annotations

from typing import List

from src.lib.s5_actionplanner.facade import PathfinderPlan


class ActionController:
    """
    Orchestrateur s6 : expose les opérations d'exécution/convert via les modules spécialisés.
    Version minimale : conversion d'un plan Pathfinder en GameAction.
    """

    def convert_pathfinder_plan_to_game_actions(self, plan: PathfinderPlan):
        # Délègue à s61_action_executor (conversion unique)
        from src.lib.s6_action.s61_action_executor import convert_pathfinder_plan_to_game_actions  # type: ignore
        return convert_pathfinder_plan_to_game_actions(plan)


def convert_pathfinder_plan_to_game_actions(plan: PathfinderPlan):
    """
    Point d'entrée fonctionnel conservé pour compatibilité : délègue au controller.
    """
    return ActionController().convert_pathfinder_plan_to_game_actions(plan)
