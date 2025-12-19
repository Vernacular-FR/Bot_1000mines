"""
Overlay visuel pour debug vision (PNG).

Génère un overlay coloré par symbole sur l'image de capture,
avec affichage du label et de la confiance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple, Optional, TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from src.config import CELL_SIZE, CELL_BORDER

if TYPE_CHECKING:
    from src.lib.s0_browser.export_context import ExportContext


class VisionOverlay:
    """Génère un overlay PNG pour visualiser les résultats vision."""

    TYPE_COLORS: Dict[str, Tuple[int, int, int]] = {
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

    BORDER_COLORS: Dict[str, Tuple[int, int, int]] = {
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

    def __init__(self, opacity: int = 140, font_size: int = 10, margin: int = 2):
        self.opacity = opacity
        self.font_size = font_size
        self.margin = margin
        self.font = self._load_font()

    def _load_font(self):
        for font_name in ("DejaVuSans.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(font_name, self.font_size)
            except OSError:
                continue
        return ImageFont.load_default()

    def render(
        self,
        base_image: Image.Image,
        matches: Dict[Tuple[int, int], dict],
        grid_origin: Tuple[int, int] = (0, 0),
        stride: Optional[int] = None,
    ) -> Image.Image:
        """Génère l'overlay sur l'image de base.
        
        Args:
            base_image: Image de fond (capture)
            matches: Dict {(row, col): {"symbol": str, "confidence": float}}
            grid_origin: Origine de la grille en pixels (x, y)
            stride: Pas entre cellules (défaut: CELL_SIZE + CELL_BORDER)
        """
        stride_px = stride if stride is not None else (CELL_SIZE + CELL_BORDER)
        
        overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        start_x, start_y = grid_origin

        for (row, col), match_data in matches.items():
            symbol = match_data.get("symbol", "unknown")
            confidence = match_data.get("confidence", 0.0)
            
            x0 = start_x + col * stride_px
            y0 = start_y + row * stride_px
            x1 = x0 + CELL_SIZE - 1
            y1 = y0 + CELL_SIZE - 1

            fill_color = self.TYPE_COLORS.get(symbol, (255, 255, 0))
            border_color = self.BORDER_COLORS.get(symbol, (255, 255, 0))
            fill = (*fill_color, self.opacity)

            # Rectangle avec bordure
            draw.rectangle([(x0, y0), (x1, y1)], outline=border_color, width=1)
            draw.rectangle(
                [(x0 + self.margin, y0 + self.margin), (x1 - self.margin, y1 - self.margin)],
                fill=fill,
            )

            # Label (symbole abrégé)
            label = symbol.replace("number_", "")
            if label == symbol:
                label = label[:3].upper()
            
            # Confiance en pourcentage
            percent = int(round(confidence * 100))
            percent = max(0, min(100, percent))

            label_x = x0 + 2
            label_y = y0 + 2
            draw.text((label_x, label_y), label, font=self.font, fill=(255, 255, 255, 255))
            
            # Pourcentage sous le label
            try:
                label_bbox = self.font.getbbox(label or "0")
                label_height = label_bbox[3] - label_bbox[1]
                percent_y = label_y + label_height + 1
                draw.text((label_x, percent_y), f"{percent}%", font=self.font, fill=(255, 255, 255, 255))
            except Exception:
                pass

        return Image.alpha_composite(base_image.convert("RGBA"), overlay)

    def render_and_save(
        self,
        base_image: Image.Image,
        matches: Dict[Tuple[int, int], dict],
        export_ctx: "ExportContext",
        grid_origin: Tuple[int, int] = (0, 0),
        stride: Optional[int] = None,
    ) -> Optional[Path]:
        """Render et sauvegarde l'overlay vision."""
        if not export_ctx.overlay_enabled:
            return None
        
        overlay_img = self.render(base_image, matches, grid_origin, stride)
        
        out_path = export_ctx.vision_overlay_path()
        overlay_img.save(out_path)
        
        # Export JSON associé
        self._save_json(matches, export_ctx, grid_origin, stride)
        
        return out_path

    def _save_json(
        self,
        matches: Dict[Tuple[int, int], dict],
        export_ctx: "ExportContext",
        grid_origin: Tuple[int, int],
        stride: Optional[int],
    ) -> Optional[Path]:
        """Sauvegarde les métadonnées vision en JSON."""
        json_path = export_ctx.json_path("s2_vision", "matches")
        
        payload = {
            "iteration": export_ctx.iteration,
            "game_id": export_ctx.game_id,
            "grid_origin": grid_origin,
            "stride": stride or (CELL_SIZE + CELL_BORDER),
            "bounds": export_ctx.capture_bounds,
            "match_count": len(matches),
            "matches": {
                f"{r}:{c}": {
                    "symbol": m.get("symbol"),
                    "confidence": m.get("confidence"),
                    "row": r,
                    "col": c,
                }
                for (r, c), m in matches.items()
            },
        }
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        
        return json_path


def vision_result_to_matches(vision_result) -> Dict[Tuple[int, int], dict]:
    """Convertit un VisionResult en dictionnaire de matches pour l'overlay."""
    matches = {}
    for match in vision_result.matches:
        coord = (match.coord.row, match.coord.col)
        matches[coord] = {
            "symbol": match.symbol,
            "confidence": match.confidence,
        }
    return matches
