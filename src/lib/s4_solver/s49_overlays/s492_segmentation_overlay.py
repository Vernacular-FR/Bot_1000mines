from __future__ import annotations

import random
from pathlib import Path
from typing import Iterable, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont

from src.lib.s1_capture.s10_overlay_utils import build_overlay_metadata_from_session
from src.lib.s4_solver.s42_csp_solver.s422_segmentation import Segmentation
from .s495_historical_canvas import build_historical_canvas_from_canvas, _parse_canvas_name

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]


def render_segmentation_overlay(
    screenshot: Optional[Path],
    bounds: Optional[Bounds],
    segmentation: Segmentation,
    stride: Optional[int],
    cell_size: Optional[int],
    export_root: Optional[Path],
) -> Optional[Path]:
    """
    Dessine un overlay coloré représentant les composantes/zonings issus de Segmentation.
    """
    meta = None
    if not (screenshot and bounds and stride and cell_size and export_root):
        meta = build_overlay_metadata_from_session()
        if not meta:
            return None
        screenshot = Path(meta["screenshot_path"])
        bounds = meta["bounds"]
        stride = meta["stride"]
        cell_size = meta["cell_size"]
        export_root = Path(meta["export_root"])
    else:
        meta = build_overlay_metadata_from_session()

    # Fond historique et bounds depuis le _hist
    if meta:
        current_canvas = Path(meta["screenshot_path"])
        hist_path = build_historical_canvas_from_canvas(current_canvas, Path(meta["export_root"]))
        if hist_path and hist_path.exists():
            screenshot = hist_path
            parsed = _parse_canvas_name(hist_path)
            if parsed:
                _, _, bounds = parsed

    image = Image.open(screenshot).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 10)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, _, _ = bounds

    colors = {}

    for comp in segmentation.components:
        if comp.id not in colors:
            colors[comp.id] = (
                random.randint(50, 200),
                random.randint(50, 200),
                random.randint(50, 200),
                180,
            )
        color = colors[comp.id]
        for zone in comp.zones:
            for (x, y) in zone.cells:
                px = (x - start_x) * stride
                py = (y - start_y) * stride
                draw.rectangle(
                    [(px, py), (px + cell_size, py + cell_size)],
                    fill=color,
                    outline=(255, 255, 255, 200),
                    width=1,
                )
            for (x, y) in zone.cells:
                px = (x - start_x) * stride
                py = (y - start_y) * stride
                draw.text((px + 2, py + 2), f"Z{zone.id}", fill=(255, 255, 255), font=font)

    # Dessiner les contraintes (cellules numérotées) en surbrillance
    constraint_cells = set()
    for zone in segmentation.zones:
        constraint_cells.update(zone.constraints)

    for (cx, cy) in constraint_cells:
        px = (cx - start_x) * stride
        py = (cy - start_y) * stride
        draw.rectangle(
            [(px, py), (px + cell_size, py + cell_size)],
            outline=(255, 0, 0, 255),
            width=2,
        )

    # Sauvegarder l'overlay
    composed = Image.alpha_composite(image, overlay)
    out_dir = Path(export_root) / "s4_solver/s42_segmentation_overlay"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{screenshot.stem}_segmentation_overlay.png"
    composed.save(out_path)

    # JSON log
    try:
        json_dir = out_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "bounds": bounds,
            "stride": stride,
            "cell_size": cell_size,
            "components": len(segmentation.components),
            "zones": len(segmentation.zones),
        }
        json_path = json_dir / f"{screenshot.stem}_segmentation_overlay.json"
        import json

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return out_path
