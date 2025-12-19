"""Planner : ordonnancement et optimisation des actions."""

from typing import List, Optional, Dict, Any

from src.lib.s0_coordinates.types import Coord, ScreenPoint, GridBounds
from src.lib.s0_coordinates.converter import CoordinateConverter
from src.lib.s4_solver.types import SolverAction, ActionType
from .types import PlannerInput, ExecutionPlan, PlannedAction


class Planner:
    """Planificateur d'actions."""

    def __init__(self, converter: Optional[CoordinateConverter] = None):
        self.converter = converter or CoordinateConverter()

    def set_converter(self, converter: CoordinateConverter) -> None:
        """Configure le convertisseur de coordonnées."""
        self.converter = converter

    def plan(self, input: PlannerInput) -> ExecutionPlan:
        """Planifie l'exécution des actions."""
        if not input.actions:
            return ExecutionPlan(actions=[], estimated_time=0.0)

        # Tri par priorité: FLAG > CLICK > GUESS
        sorted_actions = self._sort_actions(input.actions)
        
        # Conversion en PlannedAction avec coordonnées écran
        planned = []
        for i, action in enumerate(sorted_actions):
            screen_point = self._get_screen_point(action.coord)
            planned.append(PlannedAction(
                coord=action.coord,
                action=action.action,
                screen_point=screen_point,
                priority=i,
                confidence=action.confidence,
            ))

        # Estimation du temps (50ms par action)
        estimated_time = len(planned) * 0.05

        return ExecutionPlan(
            actions=planned,
            estimated_time=estimated_time,
            metadata={
                "total_actions": len(planned),
                "flags": len([a for a in planned if a.action == ActionType.FLAG]),
                "clicks": len([a for a in planned if a.action == ActionType.CLICK]),
                "guesses": len([a for a in planned if a.action == ActionType.GUESS]),
            },
        )

    def _sort_actions(self, actions: List[SolverAction]) -> List[SolverAction]:
        """Trie les actions par priorité."""
        # Ordre: FLAG d'abord, puis CLICK, puis GUESS
        priority_map = {
            ActionType.FLAG: 0,
            ActionType.CLICK: 1,
            ActionType.GUESS: 2,
        }
        return sorted(actions, key=lambda a: priority_map.get(a.action, 99))

    def _get_screen_point(self, coord: Coord) -> ScreenPoint:
        """Convertit une coordonnée grille en point écran centré."""
        x, y = self.converter.grid_to_screen_centered(coord.row, coord.col)
        return ScreenPoint(x=x, y=y)


# === API fonctionnelle ===

_default_planner: Optional[Planner] = None


def _get_planner() -> Planner:
    global _default_planner
    if _default_planner is None:
        _default_planner = Planner()
    return _default_planner


def set_planner_converter(converter: CoordinateConverter) -> None:
    """Configure le convertisseur pour le planner par défaut."""
    _get_planner().set_converter(converter)


def plan(input: PlannerInput) -> ExecutionPlan:
    """Planifie l'exécution des actions."""
    return _get_planner().plan(input)
