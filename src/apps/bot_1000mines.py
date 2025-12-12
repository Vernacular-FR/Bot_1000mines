from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from src.lib.s0_interface.s03_Coordonate_system import CanvasLocator
from src.lib.s1_capture.s11_canvas_capture import CanvasCaptureBackend
from src.services.s1_zone_capture_service import ZoneCaptureService
from src.services.s2_vision_analysis_service import VisionAnalysisService
from src.services.s1_session_setup_service import SessionSetupService


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

        return True
