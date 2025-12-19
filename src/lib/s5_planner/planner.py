"""Planification et ordonnancement des actions."""

import time
from typing import List, Optional

from src.lib.s0_coordinates import CoordinateConverter
from src.lib.s0_coordinates.types import ScreenPoint
from src.lib.s4_solver.types import SolverAction, ActionType
from src.lib.s0_browser import click_left, click_right
from .types import PlannerInput, ExecutionPlan, PlannedAction


def plan(
    input: PlannerInput, 
    converter: Optional[CoordinateConverter] = None,
    driver: Optional[any] = None,
    extractor: Optional[any] = None
) -> ExecutionPlan:
    """Convertit les actions solver en plan d'exécution et les exécute si le driver est fourni."""
    planned_actions: List[PlannedAction] = []
    
    # Trier par priorité : flags d'abord, puis safe
    flags = [a for a in input.actions if a.action == ActionType.FLAG]
    safes = [a for a in input.actions if a.action == ActionType.SAFE]
    
    def execute_and_track(action: SolverAction, priority: int) -> Optional[PlannedAction]:
        rel_point = None
        if converter:
            try:
                # coord est (col, row)
                # grid_to_canvas retourne (x, y) relatif à l'anchor
                canvas_x, canvas_y = converter.grid_to_canvas(action.coord[1], action.coord[0])
                rel_x = canvas_x + converter.cell_center_offset
                rel_y = canvas_y + converter.cell_center_offset
                rel_point = ScreenPoint(x=rel_x, y=rel_y)
            except Exception:
                pass
        
        pa = PlannedAction(
            coord=action.coord,
            action=action.action,
            screen_point=rel_point, # On stocke le point relatif ici
            priority=priority,
            confidence=action.confidence,
            reasoning=action.reasoning,
        )
        
        # Exécution en temps réel si driver fourni
        if driver and rel_point:
            lives_before = None
            if extractor:
                try:
                    lives_before = extractor.get_game_info().lives
                except Exception:
                    pass

            success = False
            if action.action == ActionType.FLAG:
                success = click_right(driver, rel_point.x, rel_point.y)
            else:
                success = click_left(driver, rel_point.x, rel_point.y)
            
            print(f"[PLANNER] {action.action.name} at {action.coord} -> {success}")
            
            # Gestion réactive du délai après explosion
            if success and action.action == ActionType.GUESS and extractor and lives_before is not None:
                try:
                    current_lives = extractor.get_game_info().lives
                    if current_lives < lives_before:
                        print(f"[PLANNER] Explosion détectée ({lives_before} -> {current_lives}). Stabilisation 2s...")
                        time.sleep(2)
                except Exception:
                    pass
        
        return pa

    priority = 0
    for action in flags:
        pa = execute_and_track(action, priority)
        planned_actions.append(pa)
        priority += 1
    
    for action in safes:
        pa = execute_and_track(action, priority)
        planned_actions.append(pa)
        priority += 1
    
    # 3. Exploration risquée (si mode exploration actif OU forcé)
    should_explore = input.is_exploring or input.force_exploration
    
    if should_explore and input.snapshot:
        from .exploration import find_exploration_candidates, select_exploration_action
        
        candidates = find_exploration_candidates(input.snapshot)
        exploration_action = select_exploration_action(candidates)
        
        if exploration_action:
            print(f"[PLANNER] Exploration action added at {exploration_action.coord} (Lives: {input.game_info.lives if input.game_info else '?'})")
            pa = execute_and_track(exploration_action, priority + 10)
            planned_actions.append(pa)

    return ExecutionPlan(
        actions=planned_actions,
        estimated_time=len(planned_actions) * 0.1,
        post_delay=0.0,
    )


def plan_simple(actions: List[SolverAction]) -> ExecutionPlan:
    """Version simplifiée sans conversion de coordonnées."""
    return plan(PlannerInput(actions=actions))
