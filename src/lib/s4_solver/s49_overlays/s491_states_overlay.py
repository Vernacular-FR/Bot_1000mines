from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image, ImageDraw, ImageFont

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

ACTIVE_COLOR = (0, 120, 255, 180)
FRONTIER_COLOR = (255, 170, 0, 200)
SOLVED_COLOR = (0, 180, 90, 180)


def render_states_overlay(
    screenshot: Path,
    bounds: Bounds,
    *,
    active: Iterable[Coord],
    frontier: Iterable[Coord],
    solved: Iterable[Coord],
    stride: int,
    cell_size: int,
    export_root: Path,
    suffix: str = "zones",
    labels: tuple[str, str, str] = ("A", "F", "S"),
) -> Path:
    """
    Génère un overlay RGBA mettant en évidence les cellules ACTIVE / FRONTIER / SOLVED.
    `labels` suit l'ordre (active, frontier, solved).
    """

    image = Image.open(screenshot).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, _, _ = bounds

    def _draw_cells(coords: Iterable[Coord], fill_color, label: str):
        for x, y in coords:
            px = (x - start_x) * stride
            py = (y - start_y) * stride
            draw.rectangle(
                [(px, py), (px + cell_size, py + cell_size)],
                fill=fill_color,
                outline=(255, 255, 255, 200),
                width=1,
            )
            draw.text((px + 3, py + 3), label, fill=(255, 255, 255, 255), font=font)

    active_label, frontier_label, solved_label = labels
    _draw_cells(active, ACTIVE_COLOR, active_label)
    _draw_cells(frontier, FRONTIER_COLOR, frontier_label)
    _draw_cells(solved, SOLVED_COLOR, solved_label)

    composed = Image.alpha_composite(image, overlay)
    out_dir = Path(export_root) / "s40_states_overlays"
    out_dir.mkdir(exist_ok=True, parents=True)
    output_path = out_dir / f"{screenshot.stem}_{suffix}.png"
    composed.save(output_path)
    return output_path
