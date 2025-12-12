from __future__ import annotations


class Minesweeper1000Bot:
    """
    Scénario minimal : session → capture → vision.
    """

    def __init__(self):
        from src.services.s1_session_setup_service import SessionSetupService

        self.session_service = SessionSetupService(auto_close_browser=True)

    def run_minimal_pipeline(self, difficulty: str | None = None) -> bool:
        init = self.session_service.setup_session(difficulty)
        if not init.get("success"):
            print(f"[SESSION] Échec init: {init.get('message')}")
            return False

        interface = init["interface"]
        from src.services.s1_zone_capture_service import ZoneCaptureService
        from src.services.s2_optimized_analysis_service import VisionAnalysisService

        capture_service = ZoneCaptureService(interface)
        vision_service = VisionAnalysisService()

        grid_bounds = (-20, -10, 20, 10)
        capture = capture_service.capture_grid_window(grid_bounds, save=True, annotate=True)
        print(f"[CAPTURE] Image sauvegardée: {capture.result.saved_path}")

        analysis = vision_service.analyze_grid_capture(capture, overlay=True)
        print(f"[VISION] {len(analysis.matches)} cellules reconnues")
        if analysis.overlay_path:
            print(f"[VISION] Overlay: {analysis.overlay_path}")

        return True
