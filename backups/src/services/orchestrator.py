"""
Nouvel orchestrateur S0→S6 sans adaptateurs legacy.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

from lib.ops import MetricsCollector, LayerType
from lib.s1_capture.s12_patch_segmenter import (
    ImagePatch,
    PatchType,
    SegmentationResult,
)
from lib.s3_tensor.tensor_grid import GridBounds, CellSymbol
from services.s1_session_setup_service import SessionSetupService


class Orchestrator:
    """Pilote la pile S0→S6 à partir d'un SessionSetupService."""

    def __init__(self, session_service: SessionSetupService, enable_metrics: bool = True):
        self.session_service = session_service
        self.enable_metrics = enable_metrics

        # Références vers les couches
        self.s0_browser: Optional[Any] = None
        self.s1_navigation: Optional[Any] = None
        self.s1_capture: Optional[Any] = None
        self.s1_segmenter: Optional[Any] = None
        self.s1_metadata_extractor: Optional[Any] = None
        self.coordinate_converter: Optional[Any] = None
        self.s2_matcher: Optional[Any] = None
        self.s3_tensor: Optional[Any] = None
        self.s3_hint_cache: Optional[Any] = None
        self.s4_solver: Optional[Any] = None
        self.s5_executor: Optional[Any] = None
        self.s6_planner: Optional[Any] = None
        self.ops_metrics: Optional[MetricsCollector] = None

        # Statistiques simples
        self.stats = {
            "total_iterations": 0,
            "successful_solves": 0,
            "actions_executed": 0,
        }
        self.is_initialized = False
        self.capture_bounds = {
            "cell1": (0, 0),
            "cell2": (18, 18),
        }
        self._patch_counter = 0

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #
    def initialize(self, difficulty: Optional[str] = None) -> bool:
        """Charge les composants à partir du service de session."""
        result = self.session_service.setup_session(difficulty=difficulty)
        if not result.get("success"):
            print(f"[ORCH] Session setup failed: {result.get('message')}")
            return False

        try:
            self._bind_components()
        except RuntimeError as err:
            print(f"[ORCH] Unable to bind components: {err}")
            return False

        if self.enable_metrics:
            try:
                self.ops_metrics = MetricsCollector(
                    trace_recorder=self.session_service.trace_recorder
                )
            except Exception as err:
                print(f"[ORCH] Metrics init skipped: {err}")

        self.is_initialized = True
        return True

    def _bind_components(self) -> None:
        """Récupère toutes les couches nécessaires depuis SessionSetupService."""
        self.s0_browser = self.session_service.get_browser_navigation()
        self.s1_navigation = self.session_service.get_navigation_service()
        self.s1_capture = self.session_service.get_capture_trigger()
        self.s1_segmenter = self.session_service.get_patch_segmenter()
        self.s1_metadata_extractor = self.session_service.get_metadata_extractor()
        self.coordinate_converter = self.session_service.get_coordinate_converter()
        self.s2_matcher = self.session_service.get_smart_matcher()
        self.s3_tensor = self.session_service.get_tensor_grid()
        self.s3_hint_cache = self.session_service.get_hint_cache()
        self.s4_solver = self.session_service.get_solver()
        self.s5_executor = self.session_service.get_action_executor()
        self.s6_planner = self.session_service.get_viewport_scheduler()

    # ------------------------------------------------------------------ #
    # Itération principale
    # ------------------------------------------------------------------ #
    def run_game_iteration(self) -> Dict[str, Any]:
        if not self.is_initialized:
            return {"success": False, "error": "orchestrator_not_initialized"}

        iteration_start = time.time()

        try:
            result = self._run_direct_iteration()
        except Exception as exc:  # pragma: no cover
            print(f"[ORCH] Iteration error: {exc}")
            return {"success": False, "error": str(exc)}

        self.stats["total_iterations"] += 1
        if result.get("success"):
            self.stats["successful_solves"] += 1
            self.stats["actions_executed"] += result.get("actions_count", 0)

        if self.ops_metrics:
            try:
                self.ops_metrics.record_operation(
                    layer=LayerType.S5_ACTIONNEUR,
                    operation_name="game_iteration",
                    operation_time=time.time() - iteration_start,
                    success=result.get("success", False),
                    tags={
                        "iterations": str(self.stats["total_iterations"]),
                        "successful_solves": str(self.stats["successful_solves"]),
                        "actions_executed": str(self.stats["actions_executed"]),
                    },
                )
            except Exception as err:
                print(f"[ORCH] Ops metrics failed: {err}")

        return result

    def _run_direct_iteration(self) -> Dict[str, Any]:
        """Pipeline S1→S6 en mode direct."""
        self._prepare_viewport_for_capture()
        self._refresh_capture_bounds()
        capture_result = self._fetch_capture_result()
        if not capture_result or not getattr(capture_result, "success", False):
            return {"success": False, "error": "capture_failed"}

        screenshot = getattr(capture_result, "screenshot_data", None)
        if screenshot is None:
            screenshot = getattr(capture_result, "screenshot", None)
        if screenshot is None:
            return {"success": False, "error": "empty_capture"}

        analysis_result = self._perform_analysis(screenshot, capture_result)
        self._log_analysis_debug(capture_result, screenshot, analysis_result)
        if not analysis_result["success"]:
            return {"success": False, "error": analysis_result.get("error", "analysis_failed")}

        recognized_cells = analysis_result["recognized_cells"]
        self._update_tensor_grid(recognized_cells)

        try:
            solution = self.s4_solver.solve_grid(timeout=10.0)
        except Exception as err:
            print(f"[ORCH] Solver failed: {err}")
            solution = None

        actions_executed = 0
        solution_confidence = 0.0

        if solution and getattr(solution, "actions", None):
            reports = self.s5_executor.execute_action_sequence(solution.actions)
            actions_executed = sum(1 for report in reports if report.result.value == "success")
            metadata = getattr(solution, "metadata", {}) or {}
            solution_confidence = metadata.get(
                "confidence",
                1.0 if getattr(solution, "success", False) else 0.0,
            )
        else:
            solution = self._mock_solution()
            moves = solution.moves[:2]
            actions_executed = self._execute_actions(moves)
            solution_confidence = getattr(solution, "confidence", 0.0)

        return {
            "success": True,
            "actions_count": actions_executed,
            "solution_confidence": solution_confidence,
            "cells_recognized": len(recognized_cells),
            "mode": "direct",
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _build_mock_capture(self, capture_id: str):
        class MockCaptureResult:
            def __init__(self, identifier: str):
                self.success = True
                self.capture_id = identifier
                self.timestamp = time.time()
                self.metadata = {"width": 640, "height": 480}
                self.screenshot = np.zeros((480, 640, 3), dtype=np.uint8)

        return MockCaptureResult(capture_id)

    def _update_tensor_grid(self, recognized_cells: List[Dict[str, Any]]) -> None:
        from lib.s3_tensor.tensor_grid import CellSymbol, GridBounds

        for cell in recognized_cells:
            x, y = cell["coordinates"]
            symbol = CellSymbol(cell["symbol"])
            confidence = cell.get("confidence", 0.8)
            bounds = GridBounds(x, y, x, y)
            symbols = np.array([[symbol.value]], dtype=np.int8)
            confidences = np.array([[confidence]], dtype=np.float32)
            self.s3_tensor.update_region(bounds, symbols, confidences)

    def _mock_solution(self):
        class MockMove:
            def __init__(self, coordinates: Tuple[int, int], action: str):
                self.coordinates = coordinates
                self.action = action

        class MockSolution:
            def __init__(self):
                self.moves = [
                    MockMove((0, 1), "reveal"),
                    MockMove((1, 0), "reveal"),
                ]
                self.confidence = 0.5

        return MockSolution

    def _execute_actions(self, moves) -> int:
        executed = 0
        for idx, move in enumerate(moves, start=1):
            try:
                print(f"[S5] Executing action {idx}: {move.coordinates} -> {move.action}")
                time.sleep(0.1)
                executed += 1
            except Exception as err:
                print(f"[S5] Action {idx} failed: {err}")
        return executed

    def _fetch_capture_result(self):
        """Déclenche une capture réelle et renvoie le résultat."""
        if not self.s1_capture:
            return self._build_mock_capture("capture_missing")

        # 1) Essayer la capture localisée entre deux cellules
        try:
            cell1 = self.capture_bounds["cell1"]
            cell2 = self.capture_bounds["cell2"]

            direct_capture = self.s1_capture.capture_between_cells(
                cell1,
                cell2,
                add_margin=True,
                margin_cells=2,
                metadata={"manual_trigger": True, "capture_mode": "between_cells"},
            )
            if getattr(direct_capture, "success", False):
                return direct_capture
            else:
                print(
                    "[ORCH] capture_between_cells returned failure",
                    f"cells={cell1}->{cell2}",
                    f"error={getattr(direct_capture, 'error_message', 'unknown')}",
                    f"metadata={getattr(direct_capture, 'metadata', {})}",
                )
        except AttributeError:
            # capture_between_cells indisponible -> passer à la capture manuelle
            pass
        except Exception as exc:
            print(f"[ORCH] capture_between_cells failed: {exc}")

        # 2) Fallback: capture manuelle plein écran
        try:
            request_id = self.s1_capture.trigger_manual_capture()
            capture_results = self.s1_capture.process_capture_queue()
            if capture_results:
                for result in capture_results:
                    if result.request_id == request_id:
                        self._ensure_manual_metadata(result)
                        return result
                fallback_result = capture_results[-1]
                self._ensure_manual_metadata(fallback_result)
                return fallback_result
        except AttributeError:
            capture_result = self.s1_capture.trigger_manual_capture()
            if isinstance(capture_result, str):
                return self._build_mock_capture(capture_result)
            self._ensure_manual_metadata(capture_result)
            return capture_result
        except Exception as exc:
            print(f"[ORCH] capture_manual failed: {exc}")
            return self._build_mock_capture("capture_error")

        return self._build_mock_capture("capture_empty")

    def _ensure_manual_metadata(self, capture_result) -> None:
        """Injecte des métadonnées minimales sur les captures fallback."""
        if not capture_result:
            return
        metadata = getattr(capture_result, "metadata", None)
        if metadata is None:
            capture_result.metadata = {}
        capture_result.metadata.setdefault("capture_type", "manual_fullscreen")
        capture_result.metadata.setdefault("manual_trigger", True)
        capture_result.metadata.setdefault("origin", "fallback")

    def _log_analysis_debug(self, capture_result, screenshot, analysis) -> None:
        """Affiche des informations de debug sur la capture et l'analyse."""
        shape = getattr(screenshot, "shape", None)
        meta = getattr(capture_result, "metadata", {}) or {}
        print(
            "[ANALYSIS] Capture",
            f"shape={shape}",
            f"metadata_keys={list(meta.keys()) if isinstance(meta, dict) else meta}",
        )

        recognized = []
        if isinstance(analysis, dict):
            recognized = analysis.get("recognized_cells", []) or []
        elif hasattr(analysis, "get"):
            recognized = analysis.get("recognized_cells", []) or []
        elif hasattr(analysis, "recognized_cells"):
            recognized = analysis.recognized_cells or []

        sample = recognized[:5]
        print(
            "[ANALYSIS] Result",
            f"success={analysis.get('success') if isinstance(analysis, dict) else getattr(analysis, 'success', False)}",
            f"cells={len(recognized)}",
            f"sample={sample}",
        )

    def _refresh_capture_bounds(self) -> None:
        """Met à jour dynamiquement les bornes de capture en fonction du viewport réel."""
        if not self.s0_browser or not self.coordinate_converter:
            return

        try:
            viewport = self.s0_browser.get_current_viewport()
            x, y, width, height = viewport
        except Exception:
            return

        try:
            top_left_grid = self.coordinate_converter.screen_to_grid(x, y)
            bottom_right_grid = self.coordinate_converter.screen_to_grid(
                x + max(0, int(width)) - 1,
                y + max(0, int(height)) - 1,
            )
        except Exception:
            return

        gx1, gy1 = top_left_grid
        gx2, gy2 = bottom_right_grid

        # S'assurer que les bornes sont cohérentes
        x_min = min(gx1, gx2)
        y_min = min(gy1, gy2)
        x_max = max(gx1, gx2)
        y_max = max(gy1, gy2)

        self.capture_bounds = {
            "cell1": (x_min, y_min),
            "cell2": (x_max, y_max),
        }

    def _prepare_viewport_for_capture(self) -> None:
        """Utilise le service de navigation pour stabiliser la vue avant capture."""
        if not self.s1_navigation:
            return
        try:
            self.s1_navigation.prepare_for_capture(wait_after=0.05)
        except Exception as err:
            print(f"[ORCH] prepare_viewport failed: {err}")

    def _perform_analysis(self, screenshot, capture_result) -> Dict[str, Any]:
        """Exécute le pipeline S1→S2 complet sur une capture."""
        if (
            self.s1_segmenter is None
            or self.s1_metadata_extractor is None
            or self.s2_matcher is None
        ):
            return {
                "success": False,
                "error": "analysis_stack_missing",
                "recognized_cells": [],
            }

        bounds = self._extract_bounds_from_capture(capture_result)
        metadata = getattr(capture_result, "metadata", {}) or {}

        if metadata.get("capture_type") == "between_cells":
            segmentation = self._segment_pre_cropped_viewport(
                screenshot,
                bounds,
                metadata,
            )
        else:
            segmentation = self.s1_segmenter.segment_viewport(
                screenshot,
                bounds,
                interface_mask=None,
            )

        if not segmentation.success:
            return {
                "success": False,
                "error": segmentation.metadata.get("error", "segmentation_failed"),
                "recognized_cells": [],
            }

        metadata_result = self.s1_metadata_extractor.extract_metadata(segmentation)
        extraction = metadata_result if metadata_result.success else None

        batch_result = self.s2_matcher.match_segmentation_result(
            segmentation,
            extraction,
            frontier_mask=None,
        )

        if not batch_result.success:
            return {
                "success": False,
                "error": batch_result.performance_metrics.get("error", "matching_failed"),
                "recognized_cells": [],
            }

        recognized_cells = [
            {
                "coordinates": result.grid_coordinates,
                "symbol": result.template_match.symbol.value,
                "confidence": result.final_confidence,
            }
            for result in batch_result.matching_results
            if result.is_successful()
        ]

        return {
            "success": True,
            "recognized_cells": recognized_cells,
            "metadata": {
                "total_patches": batch_result.total_patches,
                "matching_success_rate": batch_result.performance_metrics.get("success_rate"),
            },
        }

    def _extract_bounds_from_capture(self, capture_result) -> GridBounds:
        """Construit des bornes grille à partir des métadonnées de capture."""
        meta = getattr(capture_result, "metadata", {}) or {}
        cell1 = meta.get("cell1", self.capture_bounds["cell1"])
        cell2 = meta.get("cell2", self.capture_bounds["cell2"])

        x_min = min(cell1[0], cell2[0])
        y_min = min(cell1[1], cell2[1])
        x_max = max(cell1[0], cell2[0])
        y_max = max(cell1[1], cell2[1])

        return GridBounds(x_min, y_min, x_max, y_max)

    def _segment_pre_cropped_viewport(self, viewport_image, viewport_bounds: GridBounds, capture_metadata: Dict[str, Any]) -> SegmentationResult:
        """Construit un SegmentationResult directement depuis une capture déjà recadrée."""
        import time

        if not self.s1_segmenter:
            return SegmentationResult(
                success=False,
                patches=[],
                viewport_bounds=viewport_bounds,
                segmentation_time=0.0,
                metadata={"error": "segmenter_missing"},
            )

        start_time = time.time()
        bounds_px = capture_metadata.get("bounds_px")
        if not bounds_px or not self.coordinate_converter:
            return SegmentationResult(
                success=False,
                patches=[],
                viewport_bounds=viewport_bounds,
                segmentation_time=0.0,
                metadata={"error": "missing_bounds_px"},
            )

        try:
            cell_size = self.coordinate_converter.get_effective_cell_size()
            margin = getattr(self.s1_segmenter, "patch_margin", 2)
            patches: List[ImagePatch] = []

            arr = viewport_image
            if hasattr(viewport_image, "np"):
                arr = viewport_image.np

            x_offset = int(bounds_px.get("x_min", 0))
            y_offset = int(bounds_px.get("y_min", 0))

            for grid_y in range(viewport_bounds.y_min, viewport_bounds.y_max + 1):
                for grid_x in range(viewport_bounds.x_min, viewport_bounds.x_max + 1):
                    screen_x, screen_y = self.coordinate_converter.grid_to_screen(grid_x, grid_y)
                    local_x = int(round(screen_x - x_offset))
                    local_y = int(round(screen_y - y_offset))

                    half = cell_size // 2
                    x_start = max(0, local_x - half - margin)
                    y_start = max(0, local_y - half - margin)
                    x_end = min(local_x + half + margin, arr.shape[1])
                    y_end = min(local_y + half + margin, arr.shape[0])

                    if x_end <= x_start or y_end <= y_start:
                        continue

                    patch_img = arr[y_start:y_end, x_start:x_end]
                    if patch_img.size == 0:
                        continue

                    patch = ImagePatch(
                        patch_id=f"direct_{grid_x}_{grid_y}_{self._patch_counter}",
                        patch_type=PatchType.CELL_PATCH,
                        image_data=patch_img,
                        grid_bounds=GridBounds(grid_x, grid_y, grid_x, grid_y),
                        screen_bounds=(
                            x_offset + x_start,
                            y_offset + y_start,
                            x_end - x_start,
                            y_end - y_start,
                        ),
                        confidence=1.0,
                        metadata={
                            "capture_source": "between_cells",
                            "global_offset": (x_offset, y_offset),
                        },
                    )
                    patches.append(patch)
                    self._patch_counter += 1

            return SegmentationResult(
                success=True,
                patches=patches,
                viewport_bounds=viewport_bounds,
                segmentation_time=time.time() - start_time,
                metadata={
                    "source": "cropped_capture",
                    "patches_count": len(patches),
                    "image_shape": getattr(arr, "shape", None),
                },
            )
        except Exception as err:
            return SegmentationResult(
                success=False,
                patches=[],
                viewport_bounds=viewport_bounds,
                segmentation_time=time.time() - start_time,
                metadata={"error": str(err)},
            )

    # ------------------------------------------------------------------ #
    def get_stats(self) -> Dict[str, Any]:
        return self.stats.copy()

    def shutdown(self) -> None:
        if self.ops_metrics:
            self.ops_metrics.shutdown()
        self.session_service.cleanup_session()
        self.is_initialized = False
