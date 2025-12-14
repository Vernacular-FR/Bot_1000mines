from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from src.lib.s0_interface.s03_Coordonate_system import CanvasLocator
from src.lib.s1_capture.s11_canvas_capture import CanvasCaptureBackend
from src.services.s1_zone_capture_service import ZoneCaptureService
from src.services.s2_vision_analysis_service import VisionAnalysisService
from src.services.s1_session_setup_service import SessionSetupService
from src.lib.s3_storage.controller import StorageController
from src.lib.s4_solver.controller import SolverController
from src.lib.s2_vision.s23_vision_to_storage import matches_to_upsert, render_solver_overlay


class Minesweeper1000Bot:
    """
    Scénario minimal : session → capture canvas bruts → vision.
    """

    def __init__(self):
        self.session_service = SessionSetupService(auto_close_browser=True)

    def run_minimal_pipeline(self, difficulty: str | None = None) -> bool:
        init = self.session_service.setup_session(difficulty)
        if not init.get("success"):
            print(f"[SESSION] Échec init: {init.get('message')}")
            return False

        interface = init["interface"]
        paths = init.get("paths", {})
        game_id = init.get("game_id")

        locator = CanvasLocator(driver=interface.browser.get_driver())
        backend = CanvasCaptureBackend(interface.browser.get_driver())
        vision_service = VisionAnalysisService(
            overlay_output_dir=paths.get("vision", "temp/s2_vision")
        )
        zone_capture_service = ZoneCaptureService(interface=interface)

        raw_canvases_dir = Path(paths.get("raw_canvases", "temp/s1_raw_canvases"))
        captures = zone_capture_service.capture_canvas_tiles(
            locator=locator,
            backend=backend,
            out_dir=raw_canvases_dir,
            game_id=game_id,
        )

        if not captures:
            print("[PIPELINE] Aucune capture canvas n'a été réalisée.")
            return False

        grid_capture = zone_capture_service.compose_from_canvas_tiles(
            captures=captures,
            grid_reference=interface.converter.grid_reference_point,
            save_dir=Path(paths.get("vision", "temp/s2_vision")),
        )

        analysis = vision_service.analyze_grid_capture(
            grid_capture,
            overlay=True,
        )
        overlay_info = analysis.overlay_path or "n/a"
        print(
            f"[VISION] Canevas composite: {len(analysis.matches)} cellules reconnues "
            f"(overlay: {overlay_info})"
        )

        storage = StorageController()
        upsert = matches_to_upsert(grid_capture.grid_bounds, analysis.matches)
        storage.upsert(upsert)

        solver = SolverController(storage)
        actions = solver.solve()
        stats = solver.get_stats()

        print(
            f"[SOLVER] Actions sûres={len(actions)} "
            f"(zones={stats.zones_analyzed}, comps={stats.components_solved}, "
            f"safe={stats.safe_cells}, flags={stats.flag_cells})"
        )

        solver_overlay_dir = Path(paths.get("solver, "temp/s4_solver"))
        capture_path = grid_capture.result.saved_path
        if capture_path:
            overlay_solver = render_solver_overlay(
                base_image_path=Path(capture_path),
                bounds=grid_capture.grid_bounds,
                actions=actions,
                output_dir=solver_overlay_dir,
            )
            if overlay_solver:
                print(f"[SOLVER] Overlay enregistré: {overlay_solver}")

        return True
