"""Génération d'overlays visuels pour le debug."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import os

from PIL import Image, ImageDraw, ImageFont

from src.config import CELL_SIZE, CELL_BORDER
from src.lib.s0_coordinates.types import Coord, GridBounds
from src.lib.s2_vision.types import VisionResult, CellMatch
from src.lib.s4_solver.types import SolverOutput, ActionType


@dataclass
class OverlayConfig:
    """Configuration des overlays."""
    cell_size: int = CELL_SIZE
    cell_border: int = CELL_BORDER
    font_size: int = 12
    alpha: int = 180
    colors: Dict[str, Tuple[int, int, int]] = None

    def __post_init__(self):
        if self.colors is None:
            self.colors = {
                "safe": (0, 255, 0),      # Vert
                "flag": (255, 0, 0),       # Rouge
                "guess": (255, 165, 0),    # Orange
                "unknown": (128, 128, 128), # Gris
                "number": (0, 0, 255),     # Bleu
                "empty": (200, 200, 200),  # Gris clair
            }


class OverlayRenderer:
    """Génère des overlays visuels."""

    def __init__(self, config: Optional[OverlayConfig] = None):
        self.config = config or OverlayConfig()
        self.cell_stride = self.config.cell_size + self.config.cell_border

    def render_vision_overlay(
        self,
        base_image: Image.Image,
        vision_result: VisionResult,
        output_path: Optional[str] = None,
    ) -> Image.Image:
        """Génère un overlay pour les résultats vision."""
        overlay = base_image.copy().convert("RGBA")
        draw = ImageDraw.Draw(overlay, "RGBA")

        for match in vision_result.matches:
            self._draw_cell_match(draw, match, vision_result.bounds)

        if output_path:
            overlay.convert("RGB").save(output_path)

        return overlay

    def render_solver_overlay(
        self,
        base_image: Image.Image,
        solver_output: SolverOutput,
        bounds: GridBounds,
        output_path: Optional[str] = None,
    ) -> Image.Image:
        """Génère un overlay pour les résultats solver."""
        overlay = base_image.copy().convert("RGBA")
        draw = ImageDraw.Draw(overlay, "RGBA")

        for action in solver_output.actions:
            self._draw_action(draw, action, bounds)

        if output_path:
            overlay.convert("RGB").save(output_path)

        return overlay

    def _draw_cell_match(
        self,
        draw: ImageDraw.Draw,
        match: CellMatch,
        bounds: GridBounds,
    ) -> None:
        """Dessine une cellule matchée."""
        rel_row = match.coord.row - bounds.min_row
        rel_col = match.coord.col - bounds.min_col
        
        x = rel_col * self.cell_stride
        y = rel_row * self.cell_stride

        # Couleur selon le symbole
        if match.symbol == "unknown":
            color = self.config.colors["unknown"]
        elif match.value >= 1:
            color = self.config.colors["number"]
        else:
            color = self.config.colors["empty"]

        # Rectangle semi-transparent
        fill = (*color, self.config.alpha)
        draw.rectangle(
            [x, y, x + self.config.cell_size, y + self.config.cell_size],
            fill=fill,
            outline=color,
        )

        # Texte du symbole
        text = match.symbol[:3] if len(match.symbol) > 3 else match.symbol
        draw.text((x + 2, y + 2), text, fill=(255, 255, 255))

    def _draw_action(
        self,
        draw: ImageDraw.Draw,
        action: Any,
        bounds: GridBounds,
    ) -> None:
        """Dessine une action solver."""
        rel_row = action.coord.row - bounds.min_row
        rel_col = action.coord.col - bounds.min_col
        
        x = rel_col * self.cell_stride
        y = rel_row * self.cell_stride

        # Couleur selon le type d'action
        if action.action == ActionType.CLICK:
            color = self.config.colors["safe"]
            symbol = "✓"
        elif action.action == ActionType.FLAG:
            color = self.config.colors["flag"]
            symbol = "⚑"
        else:
            color = self.config.colors["guess"]
            symbol = "?"

        # Rectangle semi-transparent
        fill = (*color, self.config.alpha)
        draw.rectangle(
            [x, y, x + self.config.cell_size, y + self.config.cell_size],
            fill=fill,
            outline=color,
            width=2,
        )

        # Symbole centré
        draw.text(
            (x + self.config.cell_size // 3, y + self.config.cell_size // 4),
            symbol,
            fill=(255, 255, 255),
        )


# === API fonctionnelle ===

_renderer: Optional[OverlayRenderer] = None


def _get_renderer() -> OverlayRenderer:
    global _renderer
    if _renderer is None:
        _renderer = OverlayRenderer()
    return _renderer


def render_vision_overlay(
    base_image: Image.Image,
    vision_result: VisionResult,
    output_path: Optional[str] = None,
) -> Image.Image:
    """Génère un overlay vision."""
    return _get_renderer().render_vision_overlay(base_image, vision_result, output_path)


def render_solver_overlay(
    base_image: Image.Image,
    solver_output: SolverOutput,
    bounds: GridBounds,
    output_path: Optional[str] = None,
) -> Image.Image:
    """Génère un overlay solver."""
    return _get_renderer().render_solver_overlay(base_image, solver_output, bounds, output_path)
