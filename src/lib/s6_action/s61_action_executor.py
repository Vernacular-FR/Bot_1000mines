from __future__ import annotations

from typing import List

from src.lib.s5_actionplanner.facade import PathfinderPlan
from src.services.s4_action_executor_service import ActionType, GameAction


def convert_pathfinder_plan_to_game_actions(plan: PathfinderPlan) -> List[GameAction]:
    """
    Convertit un plan Pathfinder (s5) en actions jeu pour l'exécuteur s6.
    Flags -> clic droit, clicks/guesses -> clic gauche.
    """
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
