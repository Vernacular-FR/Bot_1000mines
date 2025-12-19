"""Façade principale du module s4_solver (boîte noire).

Le game_loop appelle uniquement solve(storage) et récupère les actions.
Toute l'orchestration interne (state_analyzer, csp_manager, overlays) est encapsulée.

Pipeline interne :
1. Snapshot mutable interne (copie du storage)
2. Status pass 1 (post-vision) → mute snapshot
3. CSP inference → mute snapshot
4. Status pass 2 (post-solver) → mute snapshot
5. Sweep → génère actions (pas de mutation)
6. Émettre upsert final (cellules dirty) + actions
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from PIL import Image

from .types import SolverInput, SolverOutput
from .runtime_state import SolverRuntime
from .s4a_status_analyzer import StatusManager
from .s4b_csp_solver.csp_manager import solve as _solve_internal
from .s4d_post_solver_sweep import build_sweep_actions
from src.lib.s3_storage.types import SolverStatus
from .s4c_overlays import (
    render_and_save_actions,
    render_and_save_combined,
    render_segmentation_overlay,
)

if TYPE_CHECKING:
    from src.lib.s3_storage import StorageController
    from src.lib.s0_browser.export_context import ExportContext


def solve(
    storage: "StorageController",
    *,
    overlay_ctx: Optional["ExportContext"] = None,
    base_image: Optional[Image.Image] = None,
    allow_guess: bool = False,
) -> SolverOutput:
    """Pipeline complet du solver (boîte noire).
    
    Utilise un SolverRuntime interne : snapshot mutable + dirty flags.
    Tous les sous-modules appliquent leurs upserts au runtime immédiatement.
    Le storage réel n'est mis à jour qu'une seule fois à la fin.
    
    Pipeline :
    1. Status pass 1 (post-vision) → upsert appliqué au runtime
    2. CSP inference → upsert appliqué au runtime
    3. Status pass 2 (post-solver) → upsert appliqué au runtime
    4. Sweep → génère actions (pas de mutation)
    5. Émettre upsert final + actions au storage
    
    Args:
        storage: Contrôleur de storage (source de vérité)
        overlay_ctx: Contexte d'export pour overlays (optionnel)
        base_image: Image de base pour overlays (optionnel)
        allow_guess: Autoriser les guess si pas d'actions certaines
    
    Returns:
        SolverOutput avec les actions à exécuter
    """
    # === INITIALISATION : SolverRuntime interne ===
    initial_snapshot = storage.get_snapshot()
    runtime = SolverRuntime(initial_snapshot)
    status_manager = StatusManager()
    
    # === PIPELINE 1 : POST-VISION ===
    # Classification topologique + FocusActualizer
    print("[SOLVER] Pipeline 1 : post-vision...")
    pipeline1_upsert = status_manager.pipeline_post_vision(
        runtime.get_snapshot(),
        overlay_ctx=overlay_ctx,
        base_image=base_image.copy() if base_image else None,
        bounds=overlay_ctx.capture_bounds if overlay_ctx else None,
        stride=overlay_ctx.capture_stride if overlay_ctx else None,
    )
    runtime.apply_upsert(pipeline1_upsert)
    runtime.clear_dirty()
    print(f"[SOLVER] Pipeline 1 : {len(pipeline1_upsert.cells)} cellules mises à jour")
    
    # === PIPELINE 2 : CSP INFERENCE ===
    # Compute sets from runtime snapshot (reflects Pipeline 1 updates)
    snapshot = runtime.get_snapshot()
    frontier = {
        coord for coord, cell in snapshot.items()
        if cell.solver_status == SolverStatus.FRONTIER
    }
    active_set = {
        coord for coord, cell in snapshot.items()
        if cell.solver_status == SolverStatus.ACTIVE
    }
    print(f"[SOLVER] Pipeline 2 : CSP (frontier={len(frontier)}, active={len(active_set)})...")
    
    solver_input = SolverInput(
        cells=snapshot,
        frontier=frontier,
        active_set=active_set,
    )
    
    need_segmentation = bool(overlay_ctx and overlay_ctx.overlay_enabled and base_image)
    solver_result = _solve_internal(
        solver_input,
        allow_guess=allow_guess,
        return_segmentation=need_segmentation,
    )
    print("[SOLVER] Pipeline 2 : CSP terminé")
    if need_segmentation:
        solver_output, segmentation = solver_result
    else:
        solver_output = solver_result
        segmentation = None
    
    # === PIPELINE 3 : POST-SOLVER ===
    # ActionMapper : mappe les actions + rétrograde les ACTIVE/FRONTIER
    pipeline2_upsert = status_manager.pipeline_post_solver(
        runtime.get_snapshot(),
        solver_output,
    )
    runtime.apply_upsert(pipeline2_upsert)
    runtime.clear_dirty()
    
    # === PIPELINE 4 : SWEEP ===
    # Génère des actions bonus (pas de mutation du runtime)
    sweep_actions = build_sweep_actions(runtime.get_snapshot())
    if sweep_actions:
        solver_output.actions.extend(sweep_actions)
    
    # === FINALISATION : Appliquer l'upsert final au storage ===
    final_upsert = runtime.get_final_upsert()
    if final_upsert.cells:
        storage.apply_upsert(final_upsert)
    
    # === OVERLAYS (si contexte fourni) ===
    if overlay_ctx and overlay_ctx.overlay_enabled and base_image:
        bounds = overlay_ctx.capture_bounds
        stride = overlay_ctx.capture_stride
        snapshot_for_overlay = runtime.get_snapshot()
        
        render_and_save_actions(
            base_image=base_image.copy(),
            actions=solver_output.actions,
            export_ctx=overlay_ctx,
            bounds=bounds,
            stride=stride,
            reducer_actions=solver_output.reducer_actions,
        )

        render_and_save_combined(
            base_image=base_image.copy(),
            cells=snapshot_for_overlay,
            actions=solver_output.actions,
            export_ctx=overlay_ctx,
            bounds=bounds,
            stride=stride,
            reducer_actions=solver_output.reducer_actions,
        )

        if segmentation:
            render_segmentation_overlay(
                base_image=base_image.copy(),
                segmentation=segmentation,
                export_ctx=overlay_ctx,
                bounds=bounds,
                stride=stride,
            )

    return solver_output
