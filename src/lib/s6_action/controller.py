from __future__ import annotations

from typing import List

from src.lib.s5_actionplanner.facade import PathfinderPlan


class ActionController:
    """
    Orchestrateur s6 : expose les opérations d'exécution/convert via les modules spécialisés.
    Version minimale : conversion d'un plan Pathfinder en GameAction.
    """

    def convert_pathfinder_plan_to_game_actions(self, plan: PathfinderPlan):
        # Import tardif pour éviter les cycles avec s4_action_executor_service
        from src.services.s4_action_executor_service import ActionType, GameAction  # type: ignore

        game_actions: List[GameAction] = []
        for action in plan.actions:
            if action.type == "flag":
                action_type = ActionType.CLICK_RIGHT
            else:
                action_type = ActionType.CLICK_LEFT
            x, y = action.cell
            game_actions.append(
                GameAction(
                    action_type=action_type,
                    grid_x=x,
                    grid_y=y,
                    confidence=action.confidence,
                    description=action.reasoning,
                )
            )
        return game_actions


def convert_pathfinder_plan_to_game_actions(plan: PathfinderPlan):
    """
    Point d'entrée fonctionnel conservé pour compatibilité : délègue au controller.
    """
    return ActionController().convert_pathfinder_plan_to_game_actions(plan)
