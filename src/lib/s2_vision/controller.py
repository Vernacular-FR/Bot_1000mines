#!/usr/bin/env python3
"""
Façade principale du module s2_vision.

Responsabilités :
- Charger le CenterTemplateMatcher et gérer les chemins.
- Orchestrer la classification d’une zone et produire éventuellement un overlay d’analyse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple, Optional

from PIL import Image

from src.config import CELL_SIZE, CELL_BORDER
from src.lib.s2_vision.s21_template_matcher import CenterTemplateMatcher, MatchResult
from src.lib.s2_vision.s22_vision_overlay import VisionOverlay, OverlayConfig


@dataclass
class VisionControllerConfig:
    manifest_path: Optional[Path] = None
    overlay_output_dir: Optional[Path] = None
    overlay_config: OverlayConfig = field(default_factory=OverlayConfig)


class VisionController:
    def __init__(self, config: VisionControllerConfig | None = None):
        self.config = config or VisionControllerConfig()
        self.matcher = CenterTemplateMatcher(self.config.manifest_path)
        self.overlay = VisionOverlay(self.config.overlay_config)
        self.cell_stride = CELL_SIZE + CELL_BORDER

    def classify_grid(
        self,
        screenshot_path: str | Path,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: Optional[int] = None,
        allowed_symbols: Optional[Tuple[str, ...]] = None,
        overlay: bool = False,
    ) -> Dict[Tuple[int, int], MatchResult]:
        image = Image.open(screenshot_path).convert("RGB")
        stride_px = stride if stride is not None else self.cell_stride
        results = self.matcher.classify_grid(
            image=image,
            grid_top_left=grid_top_left,
            grid_size=grid_size,
            stride=stride_px,
            allowed_symbols=allowed_symbols,
        )

        if overlay:
            overlay_img = self.overlay.render(
                base_image=image,
                grid_top_left=grid_top_left,
                grid_size=grid_size,
                results=results,
                stride=stride_px,
            )
            self.overlay.save(overlay_img, screenshot_path, self.config.overlay_output_dir)

        return results

