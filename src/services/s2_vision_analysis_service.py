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


@dataclass
class VisionAnalysisResult:
    matches: Dict[Tuple[int, int], MatchResult]
    overlay_path: Optional[Path] = None


class VisionAnalysisService:
    """Façade métier s2 : classification d'une zone capturée."""

    def __init__(
        self,
        manifest_path: Optional[str | Path] = None,
        overlay_output_dir: Optional[str | Path] = None,
    ) -> None:
        config = VisionControllerConfig(
            manifest_path=Path(manifest_path) if manifest_path else None,
            overlay_output_dir=Path(overlay_output_dir) if overlay_output_dir else None,
        )
        self.controller = VisionController(config)

    def analyze_grid_capture(
        self,
        capture: GridCapture,
        *,
        allowed_symbols: Optional[Tuple[str, ...]] = None,
        overlay: bool = False,
    ) -> VisionAnalysisResult:
        screenshot_path = self._ensure_capture_saved(capture)
        left, top, right, bottom = capture.grid_bounds
        grid_width = right - left + 1
        grid_height = bottom - top + 1

        matches = self.controller.classify_grid(
            screenshot_path=screenshot_path,
            grid_top_left=(left, top),
            grid_size=(grid_width, grid_height),
            stride=capture.cell_stride,
            allowed_symbols=allowed_symbols,
            overlay=overlay,
        )

        overlay_path = None
        if overlay and self.controller.config.overlay_output_dir:
            overlay_path = (
                Path(self.controller.config.overlay_output_dir)
                / (Path(screenshot_path).stem + "_overlay.png")
            )

        return VisionAnalysisResult(matches=matches, overlay_path=overlay_path)

    def _ensure_capture_saved(self, capture: GridCapture) -> str:
        saved_path = capture.result.saved_path
        if saved_path:
            return saved_path

        target_dir = Path("temp/s2_vision")
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        saved_path = str(target_dir / filename)
        capture.result.image.save(saved_path)
        capture.result.saved_path = saved_path
        return saved_path