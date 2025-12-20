"""Boucle de jeu : orchestration séquentielle des modules (boîtes noires).

Le game_loop ne gère que :
- L'ordre d'appel des modules
- Les itérations
- La détection de fin de partie

Chaque module est autonome et gère sa propre logique interne.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Any, Optional
from pathlib import Path
from selenium.common.exceptions import StaleElementReferenceException

from src.lib.s1_capture import capture_all_canvases
from src.lib.s2_vision import analyze_image, VisionOverlay, vision_result_to_matches
from src.lib.s3_storage import LogicalCellState, SolverStatus
from src.lib.s4_solver import solve
from src.lib.s5_planner import plan, PlannerInput
from src.lib.s0_browser.export_context import ExportContext
from src.lib.s0_interface.s07_overlay import StatusCellData, ActionCellData
from .s0_session_service import restart_game
from src.config import CELL_SIZE, CELL_BORDER

from .s0_session_service import Session


def _update_ui_overlay(session: Session, bounds, solver_output, snapshot_override=None) -> None:
    """Met à jour les overlays UI temps réel avec les données du solver.
    
    Args:
        snapshot_override: Si fourni, utilise ce snapshot au lieu de celui dans solver_output
    """
    if not session.ui_controller:
        return
    
    try:
        # Utiliser le snapshot fourni, sinon fallback sur post-pipeline1
        if snapshot_override is not None:
            snapshot = snapshot_override
        elif solver_output.snapshot_post_pipeline1:
            snapshot = solver_output.snapshot_post_pipeline1
        else:
            snapshot = session.storage.get_snapshot()  # Fallback si pas disponible
        
        # Convertir snapshot en StatusCellData (filtrer seulement ACTIVE/FRONTIER/TO_VISUALIZE)
        # Les coordonnées doivent être ABSOLUES (grille globale) car le canvas est ancré sur #anchor
        status_cells = []
        for (col, row), cell in snapshot.items():
            status = cell.solver_status.name if hasattr(cell.solver_status, 'name') else str(cell.solver_status)
            if status in ('ACTIVE', 'FRONTIER', 'TO_VISUALIZE', 'JUST_VISUALIZED', 'MINE', 'SOLVED'):
                # Déterminer le focus_level à envoyer
                focus_level = None
                if status == 'ACTIVE':
                    focus_level = cell.focus_level_active.name if hasattr(cell.focus_level_active, 'name') else str(cell.focus_level_active)
                elif status == 'FRONTIER':
                    focus_level = cell.focus_level_frontier.name if hasattr(cell.focus_level_frontier, 'name') else str(cell.focus_level_frontier)
                
                status_cells.append(StatusCellData(
                    col=col,  # Coordonnée absolue
                    row=row,  # Coordonnée absolue
                    status=status.replace('JUST_VISUALIZED', 'TO_VISUALIZE'),
                    focus_level=focus_level
                ))
        
        # Convertir actions en ActionCellData
        action_cells = []
        for action in solver_output.actions:
            col, row = action.coord
            action_type = action.action.name if hasattr(action.action, 'name') else str(action.action)
            action_cells.append(ActionCellData(
                col=col,  # Coordonnée absolue
                row=row,  # Coordonnée absolue
                type=action_type,
                confidence=getattr(action, 'confidence', 1.0),
            ))
        
        # Mettre à jour les données UI
        session.ui_controller.update_status(session.driver, status_cells)
        session.ui_controller.update_actions(session.driver, action_cells)
        
    except Exception as e:
        pass  # Silencieux pour ne pas interrompre le pipeline


@dataclass
class IterationResult:
    """Résultat d'une itération."""
    success: bool
    actions_executed: int
    duration: float
    metadata: Dict[str, Any]


def run_iteration(
    session: Session,
    iteration: int = 0,
    export_ctx: Optional[ExportContext] = None,
) -> IterationResult:
    """Exécute une itération du pipeline (appels séquentiels aux modules)."""
    start_time = time.time()
    
    if export_ctx:
        export_ctx.iteration = iteration

    # Rafraîchir la position de l'anchor pour gérer les mouvements du viewport
    session.converter.refresh_anchor()

    try:
        # 1. CAPTURE (boîte noire)
        capture_result = capture_all_canvases(
            session.driver,
            save=bool(export_ctx and export_ctx.overlay_enabled),
            save_dir=str(export_ctx.get_capture_dir()) if export_ctx and export_ctx.overlay_enabled else None,
            game_id=session.game_id,
        )
        print(f"[CAPTURE] {capture_result.canvas_count} canvas")

        # --- 2. VISION ---
        bounds = capture_result.metadata.get("grid_bounds") or capture_result.grid_bounds
        known_set = session.storage.get_known()
        
        # Propager les métadonnées de capture pour les overlays (solver/vision)
        if export_ctx:
            export_ctx.capture_bounds = (bounds.min_col, bounds.min_row, bounds.max_col, bounds.max_row)
            export_ctx.capture_stride = CELL_SIZE + CELL_BORDER
            export_ctx.capture_path = getattr(capture_result, "composite_path", None)

        vision_result = analyze_image(
            capture_result.composite_image,
            bounds=bounds,
            cell_size=CELL_SIZE,
            known_set=known_set or None,
        )
        print(f"[VISION] {vision_result.cell_count} cellules")
        
        # 2.5. Overlay vision (si activé)
        if export_ctx and export_ctx.overlay_enabled and capture_result.composite_image:
            stride = CELL_SIZE + CELL_BORDER
            vision_overlay = VisionOverlay()
            matches_dict = vision_result_to_matches(vision_result)
            vision_overlay.render_and_save(
                base_image=capture_result.composite_image,
                matches=matches_dict,
                export_ctx=export_ctx,
                grid_origin=(-bounds.min_col * stride, -bounds.min_row * stride),
                stride=stride,
            )

        # --- 3. STORAGE ---
        symbol_counts = session.storage.update_from_vision(vision_result)
        unrevealed = symbol_counts.get('unrevealed', 0)
        revealed = sum(v for k, v in symbol_counts.items() if k != 'unrevealed')
        print(f"[STORAGE] unrevealed={unrevealed}, revealed={revealed}")

        # --- 4. SOLVER ---
        solver_output = solve(
            session.storage,
            overlay_ctx=export_ctx,
            base_image=capture_result.composite_image,
        )
        print(f"[SOLVER] {len(solver_output.actions)} actions")
        
        # --- 4.5. UI OVERLAY (temps réel - progression 3 étapes) ---
        if session.ui_controller:
            # Étape 1: État brut avant solver (status_1.png)
            if solver_output.snapshot_pre_solver:
                _update_ui_overlay(session, bounds, solver_output, snapshot_override=solver_output.snapshot_pre_solver)
                time.sleep(0.15)  # Délai pour visualiser
            
            # Étape 2: Après StatusAnalyzer, avant CSP (status_2.png)
            if solver_output.snapshot_post_pipeline1:
                _update_ui_overlay(session, bounds, solver_output, snapshot_override=solver_output.snapshot_post_pipeline1)
                time.sleep(0.15)  # Délai pour visualiser
            
            # Étape 3: Après CSP, état final (status_3.png)
            if solver_output.snapshot_post_solver:
                _update_ui_overlay(session, bounds, solver_output, snapshot_override=solver_output.snapshot_post_solver)
            else:
                _update_ui_overlay(session, bounds, solver_output)  # Fallback classique

        # --- 5. PLANNER ---
        # 5.1 Extraction des infos de jeu (score, vies) pour la boucle
        game_info = session.extractor.get_game_info()
        print(f"[GAME INFO] Score: {game_info.score}, Lives: {game_info.lives}")

        # 5.2 Gestion de l'état d'exploration
        from src.config import EXPLORATION_CONFIG
        
        # Déclenchement standard (si on a des vies en rab)
        if game_info.lives > 1:
            # Déclenchement si peu d'actions
            if not session.is_exploring and len(solver_output.actions) < EXPLORATION_CONFIG['min_safe_actions']:
                session.is_exploring = True
                session.exploration_start_lives = game_info.lives
                print(f"[GAME] Mode exploration activé (actions={len(solver_output.actions)} < {EXPLORATION_CONFIG['min_safe_actions']}, lives={game_info.lives})")
            
            # Arrêt si on a perdu une vie
            if session.is_exploring and game_info.lives < session.exploration_start_lives:
                session.is_exploring = False
                print(f"[GAME] Mode exploration désactivé (vie perdue, lives={game_info.lives})")
        else:
            session.is_exploring = False

        # Détection état bloqué (stuck) -> Force exploration
        force_exploration = False
        snapshot = session.storage.get_snapshot()
        if snapshot:
            # On considère comme progrès : les cellules révélées ET les drapeaux
            revealed_count = sum(1 for c in snapshot.values() if c.logical_state != LogicalCellState.UNREVEALED)
            flag_count = sum(1 for c in snapshot.values() if c.logical_state == LogicalCellState.UNREVEALED and c.solver_status == SolverStatus.MINE)
            current_state = revealed_count + flag_count
            
            if session.last_state == current_state:
                session.same_state_count += 1
                if session.same_state_count >= 2: # Seuil à 2 itérations sans progrès
                    print(f"[GAME] Bloqué depuis {session.same_state_count} itérations (état inchangé) -> FORCE EXPLORATION")
                    force_exploration = True
            else:
                session.same_state_count = 0
            session.last_state = current_state

        # Arrêt si plus de vies (seule condition d'échec critique)
        if game_info.lives == 0:
            print("[GAME] Perdu (0 vies)")
            return IterationResult(
                success=False,
                actions_executed=0,
                duration=time.time() - start_time,
                metadata={"game_over": True}
            )

        # 5.3 Lecture de l'état de contrôle UI
        auto_exploration = False  # Valeur par défaut : désactivé
        if session.ui_controller:
            try:
                control_state = session.ui_controller.get_control_state(session.driver)
                auto_exploration = control_state.auto_exploration
            except Exception as e:
                print(f"[UI] Erreur lecture control state: {e}")

        execution_plan = plan(
            input=PlannerInput(
                actions=solver_output.actions,
                game_info=game_info,
                snapshot=session.storage.get_snapshot(),
                is_exploring=session.is_exploring,
                force_exploration=force_exploration,
                auto_exploration=auto_exploration,
                iteration=iteration
            ),
            converter=session.converter,
            driver=session.driver,
            extractor=session.extractor
        )

        # 5.3 Synchronisation des actions d'exploration avec le storage (To_visualize)
        # Note: Les actions ont déjà été exécutées par le planner
        from src.lib.s4_solver.types import ActionType as SolverActionType
        exploration_actions = [
            a for a in execution_plan.actions 
            if a.action == SolverActionType.GUESS and a.coord not in [sa.coord for sa in solver_output.actions]
        ]
        if exploration_actions:
            from src.lib.s4_solver.types import SolverAction, ActionType as SolverActionType
            from src.lib.s4_solver.s4a_status_analyzer.action_mapper import ActionMapper
            
            mapper = ActionMapper()
            # Convertir PlannedAction en SolverAction pour le mapper
            solver_guesses = [
                SolverAction(coord=a.coord, action=SolverActionType.GUESS, confidence=a.confidence, reasoning=a.reasoning)
                for a in exploration_actions
            ]
            upsert = mapper.map_actions(session.storage.get_snapshot(), solver_guesses)
            session.storage.apply_upsert(upsert)
            print(f"[STORAGE] {len(exploration_actions)} actions d'exploration ajoutées à To_visualize")

        # Check if planner returned empty plan due to disabled exploration
        if execution_plan.action_count == 0 and not auto_exploration:
            print("[GAME] Pas d'actions - Exploration auto désactivée. Bot en pause.")
            session.bot_running = False
            if session.ui_controller:
                try:
                    session.ui_controller.show_toast(
                        session.driver, 
                        "⏸️ Pas d'actions safe - Exploration auto désactivée", 
                        "warning"
                    )
                except Exception:
                    pass
            return IterationResult(
                success=True,
                actions_executed=0,
                duration=time.time() - start_time,
                metadata={"paused": True, "reason": "auto_exploration_disabled"}
            )

        # Affichage du score final de l'itération
        print(f"[ITERATION {iteration+1}] Final Score: {game_info.score}")

        return IterationResult(
            success=True, # L'exécution est maintenant intégrée au planner
            actions_executed=len(execution_plan.actions),
            duration=time.time() - start_time,
            metadata={
                "vision_count": vision_result.cell_count,
                "solver_actions": len(solver_output.actions),
            },
        )

    except StaleElementReferenceException:
        print("[WARNING] Viewport instable (mouvement manuel ?), capture ignorée.")
        return IterationResult(
            success=True, # On considère ça comme un succès vide pour ne pas arrêter la boucle
            actions_executed=0,
            duration=time.time() - start_time,
            metadata={"warning": "stale_element_reference"},
        )

    except Exception as e:
        import traceback
        print(f"[ERROR ITERATION] {type(e).__name__}: {e}")
        traceback.print_exc()
        return IterationResult(
            success=False,
            actions_executed=0,
            duration=time.time() - start_time,
            metadata={"error": str(e), "error_type": type(e).__name__},
        )


def run_game(
    session: Session,
    max_iterations: int = 500,
    delay: float = 1,
    overlay_enabled: bool = False,
) -> Dict[str, Any]:
    """Exécute la boucle de jeu complète, avec contrôles UI (pause/restart)."""
    while True:
        total_actions = 0
        iterations = 0
        
        export_ctx = None
        if overlay_enabled:
            export_ctx = ExportContext.create(
                game_id=session.game_id,
                overlay_enabled=True,
            )
            print(f"[OVERLAY] Export: {export_ctx.export_root}")
        
        for i in range(max_iterations):
            # Vérifier si restart demandé via UI
            if session.ui_controller and session.ui_controller.is_restart_requested(session.driver):
                print("[BOT] Restart demandé via UI, nouvelle partie...")
                restart_game(session)
                session.game_id = None
                break  # Sortir de la boucle d'itérations pour restart
            
            # Vérifier si redémarrage manuel détecté (clic bouton restart/difficulté)
            if session.ui_controller and session.ui_controller.is_manual_restart_requested(session.driver):
                print("[BOT] Redémarrage manuel détecté! Nouvelle partie...")
                # Redémarrer complètement la partie
                restart_game(session)
                session.game_id = None
                break  # Sortir de la boucle d'itérations pour restart
            
            # Vérifier si bot en pause via UI
            if session.ui_controller:
                while not session.ui_controller.is_bot_running(session.driver):
                    time.sleep(0.5)  # Attendre que le bot soit relancé
                    # Vérifier restart pendant la pause
                    if session.ui_controller.is_restart_requested(session.driver):
                        print("[BOT] Restart demandé pendant pause, nouvelle partie...")
                        restart_game(session)
                        session.game_id = None
                        break
                    # Vérifier redémarrage manuel pendant la pause
                    if session.ui_controller.is_manual_restart_requested(session.driver):
                        print("[BOT] Redémarrage manuel détecté pendant pause!")
                        # Redémarrer complètement la partie
                        restart_game(session)
                        session.game_id = None
                        break  # Sortir de la boucle de pause et d'itérations
            
            iterations += 1
            print(f"\n{'='*80}")
            print(f"ITÉRATION {i+1}")
            print(f"{'='*80}")
            
            result = run_iteration(session, iteration=i, export_ctx=export_ctx)
            total_actions += result.actions_executed
            
            if not result.success:
                if result.metadata.get("game_over"):
                    break
                if result.actions_executed > 0:
                    print(f"[GAME] Attention itération {i+1} : erreurs partielles, mais {result.actions_executed} actions exécutées. Continuation.")
                else:
                    print(f"[GAME] Erreur itération {i+1}")
                    break
            
            if result.actions_executed == 0:
                print(f"[GAME] Attention itération {i+1} : 0 actions exécutées.")
            
            time.sleep(delay)
        
        print(f"[GAME] {iterations} itérations, {total_actions} actions")
        
        # Fin de partie : mettre le bot en pause et attendre l'utilisateur
        if session.ui_controller:
            print("[BOT] Partie terminée. Bot en pause - utilisez les boutons de l'overlay pour continuer")
            session.ui_controller.set_bot_running(session.driver, False)
            print("[BOT] ⚡ Partie prête ! Appuyez sur Start (F5) pour commencer")
            
            # Attendre que l'utilisateur relance via l'overlay
            waiting_for_restart = True
            while waiting_for_restart:
                time.sleep(0.5)
                
                # Vérifier si auto-restart demandé (bouton "Start New Game" F6)
                if session.ui_controller.is_auto_restart_requested(session.driver):
                    print("[BOT] Auto-restart demandé via UI")
                    restart_game(session)
                    session.game_id = None
                    waiting_for_restart = False
                    break
                
                # Vérifier si redémarrage manuel détecté
                if session.ui_controller.is_manual_restart_requested(session.driver):
                    print("[BOT] Redémarrage manuel détecté")
                    restart_game(session)
                    session.game_id = None
                    waiting_for_restart = False
                    break
        else:
            # Pas d'UI controller : fallback sur input terminal
            restart_answer = input("Relancer une partie ? (y/N): ").strip().lower()
            if restart_answer != "y":
                return {
                    "iterations": iterations,
                    "total_actions": total_actions,
                    "success": True,
                    "export_root": str(export_ctx.export_root) if export_ctx else None,
                    "restart": False,
                }
            restart_game(session)
            session.game_id = None
        
        # Reboucler pour nouvelle partie
        continue
