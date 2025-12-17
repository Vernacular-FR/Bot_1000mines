from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple, Optional

from src.lib.s1_capture.s10_overlay_utils import build_overlay_metadata_from_session
from src.lib.s3_storage.facade import (
    ActiveRelevance,
    FrontierRelevance,
    GridCell,
    SolverStatus,
)
from .s495_historical_canvas import build_historical_canvas_from_canvas, _parse_canvas_name

from PIL import Image, ImageDraw, ImageFont

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

ACTIVE_TO_REDUCE_COLOR = (0, 120, 255, 200)
ACTIVE_REDUCED_COLOR = (0, 120, 255, 90)
FRONTIER_TO_PROCESS_COLOR = (255, 200, 0, 200)
FRONTIER_PROCESSED_COLOR = (255, 200, 0, 90)
SOLVED_COLOR = (0, 180, 90, 90)
TOVIZ_COLOR = (0, 0, 0, 200)


def render_states_overlay(
    screenshot: Optional[Path],
    bounds: Optional[Bounds],
    *,
    cells: Dict[Coord, GridCell],
    stride: Optional[int],
    cell_size: Optional[int],
    export_root: Optional[Path],
    suffix: str = "zones",
) -> Path:
    """
    Génère un overlay RGBA mettant en évidence les cellules avec focus explicite :
    - FRONTIER_TO_PROCESS / FRONTIER_PROCESSED
    - ACTIVE_TO_REDUCE / ACTIVE_REDUCED
    - SOLVED
    - TO_VISUALIZE (noir)
    """

    meta = None
    if not (screenshot and bounds and stride and cell_size and export_root):
        meta = build_overlay_metadata_from_session()
        if not meta:
            return None  # type: ignore
        screenshot = Path(meta["screenshot_path"])
        bounds = meta["bounds"]
        stride = meta["stride"]
        cell_size = meta["cell_size"]
        export_root = Path(meta["export_root"])
    else:
        meta = build_overlay_metadata_from_session()

    # Canvas historique (bounds et fond du _hist)
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
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, _, _ = bounds

    active_to_reduce: set[Coord] = set()
    active_reduced: set[Coord] = set()
    frontier_to_process: set[Coord] = set()
    frontier_processed: set[Coord] = set()
    solved: set[Coord] = set()
    to_visualize: set[Coord] = set()

    for coord, cell in cells.items():
        if cell.solver_status == SolverStatus.ACTIVE:
            if cell.focus_level_active not in {ActiveRelevance.TO_REDUCE, ActiveRelevance.REDUCED}:
                raise ValueError(f"focus_level_active incohérent pour ACTIVE {coord}: {cell.focus_level_active}")
            if cell.focus_level_frontier is not None:
                raise ValueError(f"focus_level_frontier doit être None pour ACTIVE {coord}")
            if cell.focus_level_active == ActiveRelevance.TO_REDUCE:
                active_to_reduce.add(coord)
            else:
                active_reduced.add(coord)
        elif cell.solver_status == SolverStatus.FRONTIER:
            if cell.focus_level_frontier not in {FrontierRelevance.TO_PROCESS, FrontierRelevance.PROCESSED}:
                raise ValueError(
                    f"focus_level_frontier incohérent pour FRONTIER {coord}: {cell.focus_level_frontier}"
                )
            if cell.focus_level_active is not None:
                raise ValueError(f"focus_level_active doit être None pour FRONTIER {coord}")
            if cell.focus_level_frontier == FrontierRelevance.TO_PROCESS:
                frontier_to_process.add(coord)
            else:
                frontier_processed.add(coord)
        elif cell.solver_status == SolverStatus.SOLVED:
            solved.add(coord)
        elif cell.solver_status == SolverStatus.TO_VISUALIZE:
            to_visualize.add(coord)

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

    _draw_cells(frontier_to_process, FRONTIER_TO_PROCESS_COLOR, "F")
    _draw_cells(frontier_processed, FRONTIER_PROCESSED_COLOR, "f")
    _draw_cells(active_to_reduce, ACTIVE_TO_REDUCE_COLOR, "A")
    _draw_cells(active_reduced, ACTIVE_REDUCED_COLOR, "a")
    _draw_cells(solved, SOLVED_COLOR, "S")
    _draw_cells(to_visualize, TOVIZ_COLOR, "V")

    composed = Image.alpha_composite(image, overlay)
    out_dir = Path(export_root) / "s4_solver/s40_states_overlays"
    out_dir.mkdir(exist_ok=True, parents=True)
    output_path = out_dir / f"{screenshot.stem}_{suffix}.png"
    composed.save(output_path)

    # JSON log
    try:
        json_dir = out_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "bounds": bounds,
            "stride": stride,
            "cell_size": cell_size,
            "counts": {
                "active_to_reduce": len(active_to_reduce),
                "active_reduced": len(active_reduced),
                "frontier_to_process": len(frontier_to_process),
                "frontier_processed": len(frontier_processed),
                "solved": len(solved),
                "to_visualize": len(to_visualize),
            },
            "active_to_reduce": sorted(active_to_reduce),
            "active_reduced": sorted(active_reduced),
            "frontier_to_process": sorted(frontier_to_process),
            "frontier_processed": sorted(frontier_processed),
            "solved_cells": sorted(solved),
            "to_visualize_cells": sorted(to_visualize),
        }
        json_path = json_dir / f"{screenshot.stem}_{suffix}.json"
        import json

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return output_path
