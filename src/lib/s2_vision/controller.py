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
        bounds_offset: Optional[Tuple[int, int]] = None,
    ) -> Dict[Tuple[int, int], MatchResult]:
        # Récupérer known_set depuis SessionContext
        from src.lib.s3_storage.s30_session_context import get_session_context
        ctx = get_session_context()
        known_set = ctx.known_set if ctx.known_set else set()
        
        image = Image.open(screenshot_path).convert("RGB")
        stride_px = stride if stride is not None else self.cell_stride
        results = self.matcher.classify_grid(
            image=image,
            grid_top_left=grid_top_left,
            grid_size=grid_size,
            stride=stride_px,
            allowed_symbols=allowed_symbols,
            known_set=known_set,
            bounds_offset=bounds_offset,
        )

        if overlay:
            # Image is already cropped, so overlay positioning starts at (0,0)
            overlay_img = self.overlay.render(
                base_image=image,
                grid_top_left=(0, 0),
                grid_size=grid_size,
                results=results,
                stride=stride_px,
            )
            self.overlay.save(overlay_img, screenshot_path, self.config.overlay_output_dir)
            # JSON sauvegardé après upsert storage dans s5_game_loop_service pour known_set à jour

        return results

