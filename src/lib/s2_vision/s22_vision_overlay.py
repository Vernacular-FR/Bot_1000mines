"""
Overlay visuel dédié au CenterTemplateMatcher.

On conserve l'esthétique de l'ancien OptimizedOverlay : codes couleur par symbole,
remplissage semi-transparent et affichage de la confiance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.config import CELL_SIZE, CELL_BORDER
from src.lib.s1_capture.s10_overlay_utils import build_overlay_metadata_from_session
from src.lib.s2_vision.s21_template_matcher import MatchResult
from src.lib.s2_vision.s23_vision_to_storage import _symbol_to_states, matches_to_upsert
from src.lib.s3_storage.facade import LogicalCellState, SolverStatus


@dataclass
class OverlayConfig:
    font_path: Path | None = None
    font_size: int = 10
    opacity: int = 140  # 0-255
    margin: int = 2


class VisionOverlay:
    """Construit un overlay visualisant les résultats du CenterTemplateMatcher."""

    TYPE_COLORS: Dict[str, tuple[int, int, int]] = {
        "empty": (128, 128, 128),
        "unrevealed": (255, 255, 255),
        "question_mark": (255, 255, 255),
        "decor": (0, 0, 0),
        "flag": (255, 0, 0),
        "mine": (0, 0, 0),
        "exploded": (0, 0, 0),
        "number_1": (0, 0, 255),
        "number_2": (0, 200, 0),
        "number_3": (255, 0, 0),
        "number_4": (128, 0, 128),
        "number_5": (255, 165, 0),
        "number_6": (0, 200, 200),
        "number_7": (0, 0, 0),
        "number_8": (80, 80, 80),
        "unknown": (255, 255, 0),
    }

    BORDER_COLORS: Dict[str, tuple[int, int, int]] = {
        "empty": (64, 64, 64),
        "unrevealed": (180, 180, 180),
        "question_mark": (180, 180, 180),
        "decor": (100, 100, 100),
        "flag": (200, 0, 0),
        "mine": (0, 0, 0),
        "exploded": (255, 0, 0),
        "number_1": (0, 70, 200),
        "number_2": (0, 150, 0),
        "number_3": (200, 0, 0),
        "number_4": (100, 0, 100),
        "number_5": (200, 100, 0),
        "number_6": (0, 150, 150),
        "number_7": (0, 0, 0),
        "number_8": (60, 60, 60),
        "unknown": (200, 200, 0),
    }

    def __init__(self, config: OverlayConfig | None = None):
        self.config = config or OverlayConfig()
        self.font = self._load_font()

    def _load_font(self):
        # 1. Font explicitement fournie
        if self.config.font_path and self.config.font_path.exists():
            try:
                return ImageFont.truetype(str(self.config.font_path), self.config.font_size)
            except OSError:
                pass

        # 2. Fonts courantes disponibles avec Pillow / système
        for font_name in ("DejaVuSans.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(font_name, self.config.font_size)
            except OSError:
                continue

        # 3. Fallback bitmap (taille fixe)
        return ImageFont.load_default()

    def render(
        self,
        base_image: Image.Image,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        results: Dict[Tuple[int, int], MatchResult],
        stride: int | None = None,
    ) -> Image.Image:
        overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        start_x, start_y = grid_top_left
        cols, rows = grid_size
        stride_px = stride if stride is not None else (CELL_SIZE + CELL_BORDER)

        for row in range(rows):
            for col in range(cols):
                result = results.get((row, col))
                if not result:
                    continue
                x0 = start_x + col * stride_px
                y0 = start_y + row * stride_px
                x1 = x0 + CELL_SIZE - 1
                y1 = y0 + CELL_SIZE - 1

                fill_color = self._fill_color(result)
                border_color = self.BORDER_COLORS.get(result.symbol, (255, 255, 0))

                draw.rectangle(
                    [(x0, y0), (x1, y1)],
                    outline=border_color,
                    width=1,
                )
                draw.rectangle(
                    [
                        (x0 + self.config.margin, y0 + self.config.margin),
                        (x1 - self.config.margin, y1 - self.config.margin),
                    ],
                    fill=fill_color,
                )

                label = result.symbol.replace("number_", "")
                if label == result.symbol:
                    label = label[:3].upper()
                percent = int(round(result.confidence * 100))
                percent = max(0, min(100, percent))
                label_x = x0 + 2
                label_y = y0 + 2
                draw.text(
                    (label_x, label_y),
                    label,
                    font=self.font,
                    fill=(255, 255, 255, 255),
                )
                label_bbox = self.font.getbbox(label or "0")
                label_height = label_bbox[3] - label_bbox[1]
                percent_y = label_y + label_height + 1
                draw.text(
                    (label_x, percent_y),
                    f"{percent}%",
                    font=self.font,
                    fill=(255, 255, 255, 255),
                )

        return Image.alpha_composite(base_image.convert("RGBA"), overlay)

    def save(self, overlay_img: Image.Image, screenshot_path: str | Path, export_root: Path | None) -> Path | None:
        """Enregistre l'overlay PNG et un JSON (matches + known_set) dans s2_vision_overlay."""
        if not export_root:
            meta = build_overlay_metadata_from_session()
            if meta:
                export_root = Path(meta["export_root"])
            else:
                return None
        out_dir = Path(export_root) / "s2_vision_overlay"
        out_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"{Path(screenshot_path).stem}_vision_overlay"
        out_path = out_dir / f"{base_name}.png"
        overlay_img.save(out_path)
        return out_path

    def save_json(
        self,
        results: Dict[Tuple[int, int], MatchResult],
        screenshot_path: str | Path,
        export_root: Path | None,
        *,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: int,
        bounds_offset: Tuple[int, int] | None = None,
    ) -> Path | None:
        """Enregistre un JSON (matches exacts passés à l'overlay + known_set)."""
        from src.lib.s3_storage.s30_session_context import get_session_context

        if not export_root:
            meta = build_overlay_metadata_from_session()
            if meta:
                export_root = Path(meta["export_root"])
            else:
                return None
        out_dir = Path(export_root) / "s2_vision_overlay" / "json"
        out_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"{Path(screenshot_path).stem}_vision_overlay"
        out_path = out_dir / f"{base_name}.json"

        ctx = get_session_context()
        known = list(ctx.known_set) if ctx.known_set else []

        payload = {
            "screenshot": str(screenshot_path),
            "grid_top_left": bounds_offset if bounds_offset else (0, 0),  # Coordonnées absolues pour cohérence
            "grid_size": grid_size,
            "stride": stride,
            "bounds_offset": bounds_offset,
            "known_set": known,
            "matches": {
                f"{r}:{c}": self._serialize_match(
                    r,
                    c,
                    m,
                    bounds_offset=bounds_offset,
                )
                for (r, c), m in results.items()
            },
            "storage_cells": self._serialize_upsert_cells(results, bounds_offset, grid_size),
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return out_path

    def _fill_color(self, result: MatchResult) -> Tuple[int, int, int, int]:
        base_color = self.TYPE_COLORS.get(result.symbol, (255, 255, 0))
        return (*base_color, self.config.opacity)

    def _serialize_match(
        self,
        row: int,
        col: int,
        match: MatchResult,
        *,
        bounds_offset: Tuple[int, int] | None,
    ) -> Dict:
        raw_state, logical_state, _ = _symbol_to_states(match.symbol)
        # Align with matches_to_upsert: JUST_VISUALIZED pour les cases révélées, NONE sinon
        solver_status = (
            SolverStatus.JUST_VISUALIZED.value
            if logical_state in (LogicalCellState.OPEN_NUMBER, LogicalCellState.EMPTY, LogicalCellState.CONFIRMED_MINE)
            else SolverStatus.NONE.value
        )
        offset_x, offset_y = bounds_offset if bounds_offset else (0, 0)
        abs_pos = (offset_x + col, offset_y + row)
        return {
            "symbol": match.symbol,
            "confidence": match.confidence,
            "position": (row, col),
            "abs_position": abs_pos,
            "logical_state": logical_state.value,
            "solver_status": solver_status,
        }

    def _serialize_upsert_cells(
        self,
        results: Dict[Tuple[int, int], MatchResult],
        bounds_offset: Tuple[int, int] | None,
        grid_size: Tuple[int, int],
    ) -> Dict[str, Dict]:
        """Reflète la sortie exact de matches_to_upsert (états mappés vision → storage)."""
        offset_x, offset_y = bounds_offset if bounds_offset else (0, 0)
        cols, rows = grid_size
        bounds = (offset_x, offset_y, offset_x + cols - 1, offset_y + rows - 1)
        upsert = matches_to_upsert(bounds, results)
        serialized = {}
        for coord, cell in upsert.cells.items():
            serialized[f"{coord[0]}:{coord[1]}"] = {
                "solver_status": cell.solver_status.value,
                "logical_state": cell.logical_state.value if hasattr(cell, "logical_state") else None,
                "raw_state": cell.raw_state.value if hasattr(cell, "raw_state") else None,
                "number_value": getattr(cell, "number_value", None),
            }
        return serialized
