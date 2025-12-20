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
    
    # --- 1. Définition des Scénarios ---
    
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

    # --- 2. Sélection du Scénario ---
    
    current_lives = input.game_info.lives if input.game_info else 3
    iteration = input.iteration
    print(f"[DEBUG] Planner received iteration={iteration}")
    
    # SCENARIO 1: PRUDENT (Début de partie)
    # On ne joue que les coups sûrs. Pas de guess du solver. Exploration lointaine si bloqué.
    if iteration <= 5:
        scenario = "PRUDENT"
        allow_solver_guesses = False
        exploration_min_dist = 5
        exploration_max_dist = 10
        
    # SCENARIO 3: DESPERATE (Fin de partie / 1 vie restante)
    # On joue tout ce qu'on a. GUESS désactivés (exploration contrôlée à la place). Exploration proche.
    elif current_lives <= 1:
        scenario = "DESPERATE"
        allow_solver_guesses = False
        exploration_min_dist = 0
        exploration_max_dist = 5
        
    # SCENARIO 2: AGGRESSIVE (Milieu de partie)
    # On a des vies, on avance. GUESS désactivés (exploration contrôlée à la place). Exploration moyenne.
    else:
        scenario = "AGGRESSIVE"
        allow_solver_guesses = False
        exploration_min_dist = 2
        exploration_max_dist = 8

    print(f"[PLANNER] Scenario: {scenario} (Iter: {iteration}, Lives: {current_lives})")

    # --- 3. Exécution des Actions ---

    # Trier par priorité : flags d'abord, puis safe, puis guess (si autorisé)
    flags = [a for a in input.actions if a.action == ActionType.FLAG]
    safes = [a for a in input.actions if a.action == ActionType.SAFE]
    guesses = [a for a in input.actions if a.action == ActionType.GUESS] if allow_solver_guesses else []
    
    priority = 0
    for action in flags:
        pa = execute_and_track(action, priority)
        planned_actions.append(pa)
        priority += 1
    
    for action in safes:
        pa = execute_and_track(action, priority)
        planned_actions.append(pa)
        priority += 1
        
    for action in guesses:
        pa = execute_and_track(action, priority)
        planned_actions.append(pa)
        priority += 1
    
    if flags or safes or guesses:
        print(f"[PLANNER] Executed: {len(flags)} flags, {len(safes)} safes, {len(guesses)} guesses")
    
    # --- 4. Exploration (si nécessaire) ---
    
    # On explore si on est bloqué (is_exploring) OU si on a forcé l'exploration
    # MAIS on n'explore PAS si on a déjà exécuté des actions (sauf si force_exploration est True)
    has_acted = len(planned_actions) > 0
    
    # [NOUVEAU] Chance de 1/3 d'exploration proactive en mode AGGRESSIVE
    import random
    proactive_exploration = False
    if scenario == "AGGRESSIVE" and current_lives > 1:
        if random.random() < 0.33:
            print(f"[PLANNER] AGGRESSIVE: Proactive exploration triggered (1/3 chance, lives={current_lives})")
            proactive_exploration = True

    should_explore = (input.is_exploring and not has_acted) or input.force_exploration or proactive_exploration
    
    # Check auto_exploration flag - si False, on ne fait JAMAIS d'exploration
    if not input.auto_exploration:
        if should_explore:
            print("[PLANNER] Auto-exploration désactivée - exploration bloquée")
        if not has_acted:
            print("[PLANNER] Auto-exploration désactivée - pas d'actions safe disponibles - pause requise")
            return ExecutionPlan(actions=[], estimated_time=0.0, post_delay=0.0)
        # On retourne les actions déjà exécutées (flags/safes) sans exploration
        return ExecutionPlan(
            actions=planned_actions,
            estimated_time=len(planned_actions) * 0.5,
            post_delay=0.0
        )
    
    if should_explore and input.snapshot:
        from .exploration import find_exploration_candidates, select_exploration_action
        
        # Définition des conditions d'arrêt du "Burst Mode"
        stop_on_first_explosion = (scenario == "PRUDENT")
        target_min_lives = 1 if scenario == "AGGRESSIVE" else 0 # Desperate va jusqu'à 0
        
        clicked_coords = set()
        initial_lives = current_lives
        
        print(f"[PLANNER] Starting Burst Exploration ({scenario}). Stop if explosion? {stop_on_first_explosion}. Target lives: {target_min_lives}")
        
        while True:
            # 1. Vérifier les conditions d'arrêt (Vies)
            if extractor:
                try:
                    real_lives = extractor.get_game_info().lives
                    
                    # Cas Prudent : On s'arrête dès qu'on perd une vie
                    if stop_on_first_explosion and real_lives < initial_lives:
                        print(f"[PLANNER] Burst stopped: Explosion detected (Prudent mode).")
                        break
                        
                    # Cas Agressif/Desperate : On s'arrête si on atteint le seuil
                    if real_lives <= target_min_lives:
                        print(f"[PLANNER] Burst stopped: Reached minimum lives ({real_lives}).")
                        break
                        
                    # Mise à jour pour la boucle
                    current_lives = real_lives
                    
                except Exception:
                    pass

            # 2. Trouver des candidats (en excluant ceux déjà cliqués)
            candidates = find_exploration_candidates(
                input.snapshot, 
                min_distance=exploration_min_dist, 
                max_distance=exploration_max_dist
            )
            # Filtrer ce qu'on a déjà cliqué dans cette boucle
            candidates = [c for c in candidates if c not in clicked_coords]
            
            if not candidates:
                if scenario == "DESPERATE":
                     print("[PLANNER] DESPERATE: No candidates found, trying global random...")
                     candidates = find_exploration_candidates(input.snapshot, min_distance=0, max_distance=100)
                     candidates = [c for c in candidates if c not in clicked_coords]
                
                if not candidates:
                    print("[PLANNER] Burst stopped: No more candidates.")
                    break

            # 3. Sélectionner et exécuter
            exploration_action = select_exploration_action(candidates, strategy_name=scenario)
            
            if exploration_action:
                print(f"[PLANNER] Burst Action ({scenario}) at {exploration_action.coord}")
                pa = execute_and_track(exploration_action, priority + 10)
                planned_actions.append(pa)
                clicked_coords.add(exploration_action.coord)
                
                # Petit délai pour laisser le jeu réagir (et potentiellement mettre à jour le DOM lives)
                time.sleep(0.15)
            else:
                break

    return ExecutionPlan(
        actions=planned_actions,
        estimated_time=len(planned_actions) * 0.1,
        post_delay=0.0,
    )


def plan_simple(actions: List[SolverAction]) -> ExecutionPlan:
    """Version simplifiée sans conversion de coordonnées."""
    return plan(PlannerInput(actions=actions))
