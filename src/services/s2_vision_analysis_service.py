#!/usr/bin/env python3
"""Service métier s2 – VisionController wrapper."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from src.lib.s2_vision.controller import VisionController, VisionControllerConfig
from src.lib.s2_vision.s21_template_matcher import MatchResult
from src.services.s1_zone_capture_service import GridCapture
from src.lib.s3_storage.s30_session_context import get_session_context, update_capture_metadata
from src.lib.s1_capture.s10_overlay_utils import build_overlay_metadata_from_session


@dataclass
class VisionAnalysisResult:
    matches: Dict[Tuple[int, int], MatchResult]
    overlay_path: Optional[Path] = None


class VisionAnalysisService:
    """Façade métier s2 : classification d'une zone capturée."""

    def __init__(
        self,
        manifest_path: Optional[str | Path] = None,
    ) -> None:
        overlay_meta = build_overlay_metadata_from_session()
        if overlay_meta:
            self.export_root = Path(overlay_meta["export_root"])
        else:
            ctx = get_session_context()
            self.export_root = Path(ctx.export_root) if ctx.export_root else None
        config = VisionControllerConfig(
            manifest_path=Path(manifest_path) if manifest_path else None,
            overlay_output_dir=self.export_root,
        )
        self.controller = VisionController(config)

    def analyze_grid_capture(
        self,
        capture: GridCapture,
        *,
        allowed_symbols: Optional[Tuple[str, ...]] = None,
        overlay: bool = False,
    ) -> VisionAnalysisResult:
        ctx = get_session_context()
        overlay_flag = overlay or bool(ctx.overlay_enabled)
        screenshot_path = self._ensure_capture_saved(capture)
        left, top, right, bottom = capture.grid_bounds
        grid_width = right - left + 1
        grid_height = bottom - top + 1

        # Publier les métadonnées de capture pour les overlays suivants (s4 solver)
        update_capture_metadata(
            saved_path=screenshot_path,
            bounds=capture.grid_bounds,
            stride=capture.cell_stride,
        )

        matches = self.controller.classify_grid(
            screenshot_path=screenshot_path,
            grid_top_left=(0, 0),  # Image is already cropped to grid boundaries
            grid_size=(grid_width, grid_height),
            stride=capture.cell_stride,
            allowed_symbols=allowed_symbols,
            overlay=overlay_flag,
            bounds_offset=(left, top),  # Pass absolute grid bounds for coordinate conversion
        )

        return VisionAnalysisResult(matches=matches, overlay_path=None)

    def _ensure_capture_saved(self, capture: GridCapture) -> str:
        saved_path = capture.result.saved_path
        if saved_path:
            return saved_path

        raise ValueError("GridCapture sans saved_path fourni à VisionAnalysisService")