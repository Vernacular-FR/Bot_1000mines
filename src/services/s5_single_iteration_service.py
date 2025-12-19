"""
Service d'itération unique pour le démineur.
Exécute une passe complète : capture → vision → storage → solver → action.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Imports du projet
from src.lib.s0_interface.s03_Coordonate_system import CanvasLocator
from src.lib.s1_capture.s11_canvas_capture import CanvasCaptureBackend
from src.lib.s4_solver.facade import SolverAction

# Imports des services
from .s1_zone_capture_service import ZoneCaptureService
from .s2_vision_analysis_service import VisionAnalysisService
from .s3_game_solver_service import GameSolverServiceV2
from src.lib.s3_storage.controller import StorageController
from src.lib.s3_storage.s30_session_context import update_capture_metadata
from src.lib.s4_solver.s40_states_manager.state_analyzer import StateAnalyzer
from src.lib.s2_vision.s23_vision_to_storage import matches_to_upsert


@dataclass
class IterationResult:
    """Résultat d'une seule itération de jeu."""
    success: bool
    actions: List[SolverAction]
    stats: Optional[Any]
    files_saved: List[str]
    message: str
    grid_bounds: Optional[tuple] = None
    iteration_num: int = 0


class SingleIterationService:
    """
    Service qui exécute une seule itération complète du pipeline de jeu.
    """

    def __init__(
        self,
        interface,
        storage: StorageController,
        capture_service: ZoneCaptureService,
        vision_service: VisionAnalysisService,
        solver_service: GameSolverServiceV2,
        state_analyzer: StateAnalyzer,
        game_paths: Dict[str, str],
        game_id: str,
        game_base_path: str,
        overlay_enabled: bool = True,
    ):
        self.interface = interface
        self.storage = storage
        self.capture_service = capture_service
        self.vision_service = vision_service
        self.solver_service = solver_service
        self.state_analyzer = state_analyzer
        self.game_paths = game_paths
        self.game_id = game_id
        self.game_base_path = game_base_path
        self.overlay_enabled = overlay_enabled

    def execute_single_pass(self, iteration_num: int = 0) -> IterationResult:
        """
        Exécute une passe complète du pipeline de jeu.
        
        Args:
            iteration_num: Numéro de l'itération (pour le logging)
            
        Returns:
            IterationResult avec les actions trouvées et les métadonnées
        """
        iter_label = f"{iteration_num:03d}"
        pass_result = {
            'success': False,
            'actions': [],
            'stats': None,
            'files_saved': [],
            'game_state': None,
            'message': '',
        }
        game_actions: list[SolverAction] = []
        
        # 1. Capture de la zone de jeu via canvases
        print("[CAPTURE] Capture de la zone de jeu (canvases)...")
        locator = CanvasLocator(driver=self.interface.browser.get_driver())
        backend = CanvasCaptureBackend(self.interface.browser.get_driver())
        raw_dir = Path(self.game_paths["raw_canvases"])
        captures = self.capture_service.capture_canvas_tiles(
            locator=locator,
            backend=backend,
            out_dir=raw_dir,
            game_id=self.game_id,
        )
        if not captures:
            return IterationResult(
                success=False,
                actions=[],
                stats=None,
                files_saved=[],
                message="Aucune capture canvas effectuée",
                iteration_num=iteration_num
            )

        grid_capture = self.capture_service.compose_from_canvas_tiles(
            captures=captures,
            grid_reference=self.interface.converter.grid_reference_point,
            save_dir=Path(self.game_paths["s1_canvas"]),
        )
        
        # Renommer la capture principale pour inclure game_id, itération et bounds
        try:
            sx, sy, ex, ey = grid_capture.grid_bounds
            target_name = f"{self.game_id}_iter{iter_label}_{sx}_{sy}_{ex}_{ey}.png"
            target_path = Path(self.game_paths["s1_canvas"]) / target_name
            current_path = Path(grid_capture.result.saved_path)
            if current_path != target_path:
                if target_path.exists():
                    target_path.unlink()
                current_path.rename(target_path)
                grid_capture.result.saved_path = str(target_path)
        except Exception as exc:
            print(f"[CAPTURE] Impossible de renommer la capture principale: {exc}")

        pass_result['files_saved'].append(grid_capture.result.saved_path)
        
        # Publier la capture + métadonnées pour les modules aval (vision/solver/overlays)
        update_capture_metadata(
            grid_capture.result.saved_path,
            grid_capture.grid_bounds,
            grid_capture.cell_stride,
        )
        zone_bounds = grid_capture.grid_bounds

        # 2. Analyse de la grille
        print("[ANALYSE] Analyse de la grille...")
        analysis = self.vision_service.analyze_grid_capture(
            grid_capture,
            overlay=True,
        )
        if analysis.overlay_path:
            pass_result['files_saved'].append(str(analysis.overlay_path))

        # 3. Sauvegarder JSON overlay avec le known_set consommé par vision (avant mise à jour storage)
        from src.lib.s2_vision.s22_vision_overlay import VisionOverlay
        overlay = VisionOverlay()
        overlay.save_json(
            analysis.matches,
            grid_capture.result.saved_path,
            Path(self.game_base_path) if self.overlay_enabled else None,
            grid_top_left=(0, 0),
            grid_size=(grid_capture.grid_bounds[2] - grid_capture.grid_bounds[0] + 1,
                      grid_capture.grid_bounds[3] - grid_capture.grid_bounds[1] + 1),
            stride=grid_capture.cell_stride,
            bounds_offset=grid_capture.grid_bounds[:2],
        )
        
        # 3b. Upsert storage puis state analyzer
        upsert = matches_to_upsert(grid_capture.grid_bounds, analysis.matches)
        self.storage.upsert(upsert)
        
        # 3c. State analyzer : promeut JUST_VISUALIZED -> ACTIVE/FRONTIER/SOLVED
        cells_snapshot = self.storage.get_cells(grid_capture.grid_bounds)
        state_upsert = self.state_analyzer.analyze_and_promote(cells_snapshot)
        if state_upsert.cells:
            self.storage.upsert(state_upsert)
        
        # Debug stockage
        active = self.storage.get_active()
        frontier = self.storage.get_frontier().coords
        print(f"[STORAGE] cells={len(upsert.cells)} active={len(active)} frontier={len(frontier)}")
        # Log rapide des premiers symboles
        sample_cells = list(upsert.cells.items())[:10]
        sample_desc = ", ".join([f"{coord}:{cell.raw_state.name}" for coord, cell in sample_cells])
        print(f"[STORAGE] échantillon cells: {sample_desc}")

        # 4. Résolution
        print("[SOLVEUR] Résolution du puzzle...")
        solve_result = self.solver_service.solve_snapshot()
        solver_actions = solve_result.get("actions", []) or []
        cleanup_actions = solve_result.get("cleanup_actions", []) or []
        reducer_actions = solve_result.get("reducer_actions", []) or []
        stats = solve_result.get("stats")
        segmentation = solve_result.get("segmentation")
        safe_cells = solve_result.get("safe_cells", [])
        total_flags = getattr(stats, "flag_cells", 0)
        
        # Log stats
        print(f"[SOLVEUR] reduc={len(reducer_actions)} solver_actions={len(solver_actions)} "
              f"cleanup_bonus={len(cleanup_actions)} (safe={len(safe_cells)}, flags={total_flags}, "
              f"zones={len(segmentation.get('zones', [])) if segmentation else 0}, "
              f"comps={len(segmentation.get('components', [])) if segmentation else 0})")

        # 5. Planification des actions
        print("[PLAN] total_actions={len(solver_actions)} deterministes_sans_guess={len([a for a in solver_actions if a.type.value != 'guess'])} "
              f"choisis={len([a for a in solver_actions if a.confidence > 0.5])}")
        
        # Retourner le résultat
        return IterationResult(
            success=True,
            actions=solver_actions,
            stats=stats,
            files_saved=pass_result['files_saved'],
            message="",
            grid_bounds=grid_capture.grid_bounds,
            iteration_num=iteration_num
        )
