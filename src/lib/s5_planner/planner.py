"""Planification et ordonnancement des actions."""

from __future__ import annotations

from typing import List, Optional

from src.lib.s0_coordinates import CoordinateConverter
from src.lib.s0_coordinates.types import ScreenPoint
from src.lib.s4_solver.types import SolverAction, ActionType
from .types import PlannerInput, ExecutionPlan, PlannedAction


def plan(input: PlannerInput, converter: Optional[CoordinateConverter] = None) -> ExecutionPlan:
    """Convertit les actions solver en plan d'exécution."""
    planned_actions: List[PlannedAction] = []
    
    # Trier par priorité : flags d'abord, puis safe
    flags = [a for a in input.actions if a.action == ActionType.FLAG]
    safes = [a for a in input.actions if a.action == ActionType.SAFE]
    
    priority = 0
    
    for action in flags:
        screen_point = None
        if converter:
            try:
                screen_point = converter.coord_to_screen_centered(
                    type('Coord', (), {'row': action.coord[1], 'col': action.coord[0]})()
                )
            except Exception:
                pass
        
        planned_actions.append(PlannedAction(
            coord=action.coord,
            action=action.action,
            screen_point=screen_point,
            priority=priority,
            confidence=action.confidence,
            reasoning=action.reasoning,
        ))
        priority += 1
    
    for action in safes:
        screen_point = None
        if converter:
            try:
                screen_point = converter.coord_to_screen_centered(
                    type('Coord', (), {'row': action.coord[1], 'col': action.coord[0]})()
                )
            except Exception:
                pass
        
        planned_actions.append(PlannedAction(
            coord=action.coord,
            action=action.action,
            screen_point=screen_point,
            priority=priority,
            confidence=action.confidence,
            reasoning=action.reasoning,
        ))
        priority += 1
    
    return ExecutionPlan(
        actions=planned_actions,
        estimated_time=len(planned_actions) * 0.1,
    )


def plan_simple(actions: List[SolverAction]) -> ExecutionPlan:
    """Version simplifiée sans conversion de coordonnées."""
    return plan(PlannerInput(actions=actions))
