"""Orchestrateur du module s4a_status_analyzer avec deux pipelines distincts.

Pipeline 1 (post-vision) :
- StatusAnalyzer : classifie les JUST_VISUALIZED en ACTIVE/FRONTIER/SOLVED/MINE
- FocusActualizer : promeut les voisins des nouvelles cellules
- Génère overlay _1

Pipeline 2 (post-solver) :
- ActionMapper : mappe les actions solver (FLAG→MINE, SAFE/GUESS→TO_VISUALIZE)
- Rétrograde les ACTIVE/FRONTIER non résolues
- Génère overlays _2 et combiné
"""

from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING
from PIL import Image

from src.lib.s3_storage.types import Coord, GridCell, StorageUpsert, SolverStatus
from .status_analyzer import StatusAnalyzer
from .focus_actualizer import FocusActualizer
from .action_mapper import ActionMapper
from src.lib.s4_solver.s4c_overlays import render_and_save_status

if TYPE_CHECKING:
    from src.lib.s0_browser.export_context import ExportContext
    from src.lib.s4_solver.types import SolverOutput


class StatusManager:
    """Orchestrateur complet du module status_analyzer avec deux pipelines."""

    def __init__(self):
        self.status_analyzer = StatusAnalyzer()
        self.focus_actualizer = FocusActualizer()
        self.action_mapper = ActionMapper()

    # ===== PIPELINE 1 : POST-VISION =====

    def pipeline_post_vision(
        self,
        cells: Dict[Coord, GridCell],
        *,
        overlay_ctx: Optional["ExportContext"] = None,
        base_image: Optional[Image.Image] = None,
        bounds: Optional[tuple[int, int, int, int]] = None,
        stride: Optional[int] = None,
    ) -> StorageUpsert:
        """Pipeline 1 : Après la vision, avant le solver.
        
        1. StatusAnalyzer : classifie les cellules en ACTIVE/FRONTIER/SOLVED/MINE
        2. FocusActualizer : promeut les voisins des NOUVELLES cellules (changement de statut)
        3. Génère overlay _1
        
        Retourne un StorageUpsert avec les statuts mis à jour et les focus promus.
        """
        # Étape 0 : Overlay des statuts (AVANT classification, état brut du storage)
        if overlay_ctx and overlay_ctx.overlay_enabled and base_image:
            render_and_save_status(
                base_image=base_image.copy(),
                cells=cells,
                export_ctx=overlay_ctx,
                bounds=bounds,
                stride=stride,
                suffix="_1"
            )

        # Étape 1 : Analyse et classification
        upsert_analysis = self.status_analyzer.analyze(
            cells,
            overlay_ctx=overlay_ctx,
            base_image=base_image,
            bounds=bounds,
            stride=stride,
        )
        
        # Étape 2 : Promotion des focus UNIQUEMENT pour les cellules qui ont changé de statut
        # (celles dans upsert_analysis.cells, pas toutes les ACTIVE/FRONTIER)
        newly_changed = set(upsert_analysis.cells.keys())
        if newly_changed:
            upsert_focus = self.focus_actualizer.promote_focus(cells, newly_changed)
            # Fusionner les upserts
            upsert_analysis.cells.update(upsert_focus.cells)
        
        # Étape 3 : Overlay des statuts (APRÈS classification)
        if overlay_ctx and overlay_ctx.overlay_enabled and base_image:
            # On applique l'upsert à un snapshot local pour l'overlay
            snapshot = {**cells, **upsert_analysis.cells}
            render_and_save_status(
                base_image=base_image.copy(),
                cells=snapshot,
                export_ctx=overlay_ctx,
                bounds=bounds,
                stride=stride,
                suffix="_2"
            )

        return upsert_analysis

    # ===== PIPELINE 2 : POST-SOLVER =====

    def pipeline_post_solver(
        self,
        cells: Dict[Coord, GridCell],
        solver_output: "SolverOutput",
        *,
        overlay_ctx: Optional["ExportContext"] = None,
        base_image: Optional[Image.Image] = None,
        bounds: Optional[tuple[int, int, int, int]] = None,
        stride: Optional[int] = None,
    ) -> StorageUpsert:
        """Pipeline 2 : Après le solver.
        
        1. ActionMapper : mappe les actions solver
           - FLAG → MINE + CONFIRMED_MINE
           - SAFE/GUESS → TO_VISUALIZE
           - Rétrograde les ACTIVE/FRONTIER non résolues
        2. StatusAnalyzer (Pass 2) : re-classifie les ACTIVE pour trouver les SOLVED
        
        Retourne un StorageUpsert avec les actions mappées et les retrogressions.
        """
        # Étape 1 : ActionMapper (mappe les actions SAFE/FLAG/GUESS)
        upsert_actions = self.action_mapper.map_actions(cells, solver_output.actions)
        
        # Étape 2 : StatusAnalyzer (Pass 2)
        # On applique les actions à un snapshot local pour voir si des ACTIVE sont maintenant SOLVED
        snapshot = {**cells, **upsert_actions.cells}
        upsert_solved = self.status_analyzer.analyze(snapshot, target_status=SolverStatus.ACTIVE)
        
        # Fusionner les upserts
        upsert_actions.cells.update(upsert_solved.cells)
        
        return upsert_actions
