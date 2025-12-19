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

from src.lib.s1_capture import capture_all_canvases
from src.lib.s2_vision import analyze_image, VisionOverlay, vision_result_to_matches
from src.lib.s3_storage import LogicalCellState
from src.lib.s4_solver import solve
from src.lib.s5_planner import plan, PlannerInput
from src.lib.s6_executor import execute, ExecutorInput
from src.lib.s0_browser.export_context import ExportContext
from .s0_session_service import restart_game
from src.config import CELL_SIZE, CELL_BORDER

from .s0_session_service import Session


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

    try:
        # 1. CAPTURE (boîte noire)
        capture_result = capture_all_canvases(
            session.driver,
            save=bool(export_ctx and export_ctx.overlay_enabled),
            save_dir=str(export_ctx.get_capture_dir()) if export_ctx and export_ctx.overlay_enabled else None,
            game_id=session.game_id,
        )
        print(f"[CAPTURE] {capture_result.canvas_count} canvas")

        # 2. VISION (boîte noire)
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

        # 3. STORAGE (boîte noire)
        symbol_counts = session.storage.update_from_vision(vision_result)
        print(f"[STORAGE] {symbol_counts}")

        # 4. SOLVER (boîte noire)
        solver_output = solve(
            session.storage,
            overlay_ctx=export_ctx,
            base_image=capture_result.composite_image,
        )
        print(f"[SOLVER] {len(solver_output.actions)} actions")

        if not solver_output.actions:
            return IterationResult(True, 0, time.time() - start_time, {"no_actions": True})

        # 5. PLANNER (boîte noire)
        execution_plan = plan(PlannerInput(actions=solver_output.actions))

        # 6. EXECUTOR (boîte noire)
        exec_result = execute(ExecutorInput(plan=execution_plan, driver=session.driver))
        print(f"[EXECUTOR] {exec_result.executed_count} actions")
        
        return IterationResult(
            success=exec_result.success,
            actions_executed=exec_result.executed_count,
            duration=time.time() - start_time,
            metadata={
                "vision_count": vision_result.cell_count,
                "solver_actions": len(solver_output.actions),
            },
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
    """Exécute la boucle de jeu complète, avec relance via bouton restart sans recréer la session."""
    while True:
        total_actions = 0
        iterations = 0
        last_state = None
        same_state_count = 0
        
        export_ctx = None
        if overlay_enabled:
            export_ctx = ExportContext.create(
                game_id=session.game_id,
                overlay_enabled=True,
            )
            print(f"[OVERLAY] Export: {export_ctx.export_root}")
        
        for i in range(max_iterations):
            iterations += 1
            result = run_iteration(session, iteration=i, export_ctx=export_ctx)
            total_actions += result.actions_executed
            
            if not result.success:
                if result.actions_executed > 0:
                    print(f"[GAME] Attention itération {i+1} : erreurs partielles, mais {result.actions_executed} actions exécutées. Continuation.")
                else:
                    print(f"[GAME] Erreur itération {i+1}")
                    break
            
            if result.actions_executed == 0:
                print(f"[GAME] Fin itération {i+1}")
                break
            
            # Détection état bloqué
            snapshot = session.storage.get_snapshot()
            if snapshot:
                current_state = sum(1 for c in snapshot.values() if c.logical_state != LogicalCellState.UNREVEALED)
                if last_state == current_state and result.actions_executed > 0:
                    same_state_count += 1
                    if same_state_count >= 3:
                        print(f"[GAME] Bloqué depuis {same_state_count} itérations")
                        break
                else:
                    same_state_count = 0
                last_state = current_state
            
            time.sleep(delay)
        
        print(f"[GAME] {iterations} itérations, {total_actions} actions")
        
        # Demander si on relance une partie via le bouton restart
        restart_answer = input("Relancer une partie ? (y/N): ").strip().lower()
        restart_requested = restart_answer == "y"

        if not restart_requested:
            return {
                "iterations": iterations,
                "total_actions": total_actions,
                "success": True,
                "export_root": str(export_ctx.export_root) if export_ctx else None,
                "restart": False,
            }

        # Relancer la partie sans recréer la session / navigateur
        restart_game(session)
        session.game_id = None  # forcer un nouvel export_root/itérations visuelles
        # Reboucler pour une nouvelle partie dans la même session (itérations remises à zéro)
        continue
