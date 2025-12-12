#!/usr/bin/env python3
"""
API minimale pour déclencher l’analyse vision.

Pensée pour être appelée depuis d’autres services (solver, outils de debug, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Optional

from PIL import Image

from src.lib.s2_vision.controller import VisionController, VisionControllerConfig
from src.lib.s2_vision.s21_template_matcher import MatchResult


class VisionAPI:
    def __init__(self, config: VisionControllerConfig | None = None):
        self.controller = VisionController(config)

    def analyze_screenshot(
        self,
        screenshot_path: str | Path,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: int = 24,
        overlay: bool = False,
        allowed_symbols: Optional[Tuple[str, ...]] = None,
    ) -> Dict[Tuple[int, int], MatchResult]:
        return self.controller.classify_grid(
            screenshot_path=screenshot_path,
            grid_top_left=grid_top_left,
            grid_size=grid_size,
            stride=stride,
            allowed_symbols=allowed_symbols,
            overlay=overlay,
        )
