"""Overlay des statuts topologiques des cellules (ACTIVE/FRONTIER/SOLVED/TO_VISUALIZE)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Tuple, Optional, TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from src.config import CELL_SIZE, CELL_BORDER
from src.lib.s3_storage.types import (
    Coord, LogicalCellState,
    ActiveRelevance,
    FrontierRelevance,
    GridCell,
    SolverStatus,
)

if TYPE_CHECKING:
    from src.lib.s0_browser.export_context import ExportContext

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

# Couleurs pour les états (identiques au legacy)
ACTIVE_TO_REDUCE_COLOR = (0, 120, 255, 200)      # Bleu vif, opaque
ACTIVE_REDUCED_COLOR = (0, 120, 255, 90)         # Bleu, 4x plus transparent
FRONTIER_TO_PROCESS_COLOR = (255, 200, 0, 200)   # Jaune vif, opaque
FRONTIER_PROCESSED_COLOR = (255, 200, 0, 90)     # Jaune, 4x plus transparent
SOLVED_COLOR = (0, 180, 90, 90)                  # Vert
TO_VISUALIZE_COLOR = (0, 0, 0, 100)              # Noir
MINE_COLOR = (255, 0, 0, 150)                    # Rouge

STATUS_COLORS = {
    "active_to_reduce": ACTIVE_TO_REDUCE_COLOR,
    "active_reduced": ACTIVE_REDUCED_COLOR,
    "frontier_to_process": FRONTIER_TO_PROCESS_COLOR,
    "frontier_processed": FRONTIER_PROCESSED_COLOR,
    "solved": SOLVED_COLOR,
    "to_visualize": TO_VISUALIZE_COLOR,
    "mine": MINE_COLOR,
}


def _load_font(size: int = 14):
    """Charge une police avec fallback."""
    for font_name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_status_overlay(
    base_image: Image.Image,
    cells: Dict[Coord, GridCell],
    bounds: Bounds,
    stride: Optional[int] = None,
    cell_size: Optional[int] = None,
) -> Image.Image:
    """
    Génère un overlay RGBA mettant en évidence les cellules avec focus explicite :
    - FRONTIER_TO_PROCESS / FRONTIER_PROCESSED
    - ACTIVE_TO_REDUCE / ACTIVE_REDUCED
    - SOLVED
    - TO_VISUALIZE (noir)
    """
    stride = stride or (CELL_SIZE + CELL_BORDER)
    cell_size = cell_size or CELL_SIZE
    
    overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(14)

    start_x, start_y, _, _ = bounds

    # Classifier les cellules par état et niveau de focus
    active_to_reduce: set[Coord] = set()
    active_reduced: set[Coord] = set()
    frontier_to_process: set[Coord] = set()
    frontier_processed: set[Coord] = set()
    solved: set[Coord] = set()
    to_visualize: set[Coord] = set()
    mine: set[Coord] = set()

    for coord, cell in cells.items():
        if cell.solver_status == SolverStatus.ACTIVE:
            if cell.focus_level_active == ActiveRelevance.TO_REDUCE:
                active_to_reduce.add(coord)
            elif cell.focus_level_active == ActiveRelevance.REDUCED:
                active_reduced.add(coord)
            else:
                # Par défaut, TO_REDUCE si pas de focus défini
                active_to_reduce.add(coord)
        elif cell.solver_status == SolverStatus.FRONTIER:
            if cell.focus_level_frontier == FrontierRelevance.TO_PROCESS:
                frontier_to_process.add(coord)
            elif cell.focus_level_frontier == FrontierRelevance.PROCESSED:
                frontier_processed.add(coord)
            else:
                # Par défaut, TO_PROCESS si pas de focus défini
                frontier_to_process.add(coord)
        elif cell.solver_status == SolverStatus.SOLVED:
            solved.add(coord)
        elif cell.solver_status == SolverStatus.TO_VISUALIZE:
            to_visualize.add(coord)
        elif cell.solver_status == SolverStatus.MINE:
            mine.add(coord)

    def _draw_cells(coords: Iterable[Coord], fill_color: Tuple, label: str):
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

    # Libellés centrés sur les niveaux de focus (comme le legacy)
    _draw_cells(frontier_to_process, FRONTIER_TO_PROCESS_COLOR, "TP")  # TO_PROCESS
    _draw_cells(frontier_processed, FRONTIER_PROCESSED_COLOR, "P")     # PROCESSED
    _draw_cells(active_to_reduce, ACTIVE_TO_REDUCE_COLOR, "TR")        # TO_REDUCE
    _draw_cells(active_reduced, ACTIVE_REDUCED_COLOR, "R")             # REDUCED
    _draw_cells(solved, SOLVED_COLOR, "S")
    _draw_cells(to_visualize, TO_VISUALIZE_COLOR, "V")
    _draw_cells(mine, MINE_COLOR, "M")

    return Image.alpha_composite(base_image.convert("RGBA"), overlay)


def render_and_save_status(
    base_image: Image.Image,
    cells: Dict[Coord, GridCell],
    export_ctx: "ExportContext",
    bounds: Optional[Bounds] = None,
    stride: Optional[int] = None,
    suffix: str = "",
) -> Optional[Path]:
    """Render et sauvegarde l'overlay des états."""
    if not export_ctx.overlay_enabled:
        return None
    
    bounds = bounds or export_ctx.capture_bounds
    if bounds is None:
        return None
    
    stride = stride or export_ctx.capture_stride or (CELL_SIZE + CELL_BORDER)
    overlay_img = render_status_overlay(base_image, cells, bounds, stride)

    out_dir = export_ctx.get_solver_overlay_dir("s4c1_status")
    
    # On ajoute le suffixe au nom de base si présent
    tag = f"s4c1_status{suffix}"
    base_name = export_ctx.solver_overlay_filename(tag)  # solver_iter_XXXX_s4c1_status_1.png
    out_path = out_dir / base_name

    overlay_img.save(out_path)
    
    # Export JSON associé (suffix aligné avec le nom de fichier)
    _save_json(cells, export_ctx, bounds, stride, out_path.stem)
    
    return out_path


def _save_json(
    cells: Dict[Coord, GridCell],
    export_ctx: "ExportContext",
    bounds: Bounds,
    stride: int,
    stem: Optional[str] = None,
) -> Optional[Path]:
    """Sauvegarde les métadonnées des états en JSON."""
    # Compter les cellules par état
    counts = {
        "active_to_reduce": 0,
        "active_reduced": 0,
        "frontier_to_process": 0,
        "frontier_processed": 0,
        "solved": 0,
        "to_visualize": 0,
    }
    
    coords_by_state = {k: [] for k in counts}
    
    for coord, cell in cells.items():
        if cell.solver_status == SolverStatus.ACTIVE:
            if cell.focus_level_active == ActiveRelevance.TO_REDUCE:
                counts["active_to_reduce"] += 1
                coords_by_state["active_to_reduce"].append(coord)
            else:
                counts["active_reduced"] += 1
                coords_by_state["active_reduced"].append(coord)
        elif cell.solver_status == SolverStatus.FRONTIER:
            if cell.focus_level_frontier == FrontierRelevance.TO_PROCESS:
                counts["frontier_to_process"] += 1
                coords_by_state["frontier_to_process"].append(coord)
            else:
                counts["frontier_processed"] += 1
                coords_by_state["frontier_processed"].append(coord)
        elif cell.solver_status == SolverStatus.SOLVED:
            counts["solved"] += 1
            coords_by_state["solved"].append(coord)
        elif cell.solver_status == SolverStatus.TO_VISUALIZE:
            counts["to_visualize"] += 1
            coords_by_state["to_visualize"].append(coord)
    
    payload = {
        "iteration": export_ctx.iteration,
        "game_id": export_ctx.game_id,
        "bounds": bounds,
        "stride": stride,
        "counts": counts,
        "active_to_reduce": sorted(coords_by_state["active_to_reduce"]),
        "active_reduced": sorted(coords_by_state["active_reduced"]),
        "frontier_to_process": sorted(coords_by_state["frontier_to_process"]),
        "frontier_processed": sorted(coords_by_state["frontier_processed"]),
        "solved_cells": sorted(coords_by_state["solved"]),
        "to_visualize_cells": sorted(coords_by_state["to_visualize"]),
    }
    
    if stem:
        # On utilise le stem du fichier image pour le JSON pour qu'ils soient alignés
        json_suffix = stem
    else:
        json_suffix = "status"
    
    json_path = export_ctx.json_path("s4c1_status", json_suffix)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    
    return json_path
