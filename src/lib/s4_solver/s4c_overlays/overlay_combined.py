"""Overlay combiné : états + actions du solver avec esthétique status overlay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, TYPE_CHECKING

from PIL import Image, ImageDraw

# Note: Cache incrémentiel retiré - trop complexe pour le bénéfice actuel

from src.config import CELL_SIZE, CELL_BORDER
from src.lib.s3_storage.types import (
    ActiveRelevance,
    FrontierRelevance,
    GridCell,
    LogicalCellState,
    SolverStatus,
)
from src.lib.s4_solver.types import SolverAction, ActionType

# Couleur unique pour tous les symboles d'actions : blanc
ACTION_SYMBOL_COLOR = (255, 255, 255, 255)

if TYPE_CHECKING:
    from src.lib.s0_browser.export_context import ExportContext

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

# Couleurs pour les états (identiques au status overlay)
ACTIVE_TO_REDUCE_COLOR = (0, 120, 255, 200)      # Bleu vif, opaque
ACTIVE_REDUCED_COLOR = (0, 120, 255, 90)         # Bleu, 4x plus transparent
FRONTIER_TO_PROCESS_COLOR = (255, 200, 0, 200)   # Jaune vif, opaque
FRONTIER_PROCESSED_COLOR = (255, 200, 0, 90)     # Jaune, 4x plus transparent
SOLVED_COLOR = (0, 180, 90, 90)                  # Vert
TO_VISUALIZE_COLOR = (0, 0, 0, 100)              # Noir
MINE_COLOR = (255, 0, 0, 150)                    # Rouge


def render_combined_overlay(
    base_image: Image.Image,
    cells: Dict[Coord, GridCell],
    actions: List[SolverAction],
    bounds: Bounds,
    stride: Optional[int] = None,
    cell_size: Optional[int] = None,
    reducer_actions: Optional[List[SolverAction]] = None,
) -> Image.Image:
    """
    Génère un overlay combiné avec zones mises à jour + actions du solver.
    """
    stride = stride or (CELL_SIZE + CELL_BORDER)
    cell_size = cell_size or CELL_SIZE
    
    # 0. Reconstituer les zones depuis cells (et valider les focus)
    active_to_reduce: set[Coord] = set()
    active_reduced: set[Coord] = set()
    frontier_to_process: set[Coord] = set()
    frontier_processed: set[Coord] = set()
    solved: set[Coord] = set()
    mine: set[Coord] = set()
    to_visualize: set[Coord] = set()

    for coord, cell in cells.items():
        if cell.solver_status == SolverStatus.ACTIVE:
            if cell.focus_level_active == ActiveRelevance.TO_REDUCE:
                active_to_reduce.add(coord)
            elif cell.focus_level_active == ActiveRelevance.REDUCED:
                active_reduced.add(coord)
            else:
                active_to_reduce.add(coord)
        elif cell.solver_status == SolverStatus.FRONTIER:
            if cell.focus_level_frontier == FrontierRelevance.TO_PROCESS:
                frontier_to_process.add(coord)
            elif cell.focus_level_frontier == FrontierRelevance.PROCESSED:
                frontier_processed.add(coord)
            else:
                frontier_to_process.add(coord)
        elif cell.solver_status == SolverStatus.SOLVED:
            solved.add(coord)
        elif cell.solver_status == SolverStatus.MINE:
            mine.add(coord)
        elif cell.solver_status == SolverStatus.TO_VISUALIZE:
            to_visualize.add(coord)

    # 1. Overlay zones en mémoire
    zone_overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    draw_zones = ImageDraw.Draw(zone_overlay)

    start_x, start_y, _, _ = bounds

    def _draw_cells(coords, fill_color):
        for x, y in coords:
            px = (x - start_x) * stride
            py = (y - start_y) * stride
            draw_zones.rectangle(
                [(px, py), (px + cell_size, py + cell_size)],
                fill=fill_color,
                outline=(255, 255, 255, 200),
                width=1,
            )

    _draw_cells(frontier_to_process, FRONTIER_TO_PROCESS_COLOR)
    _draw_cells(frontier_processed, FRONTIER_PROCESSED_COLOR)
    _draw_cells(active_to_reduce, ACTIVE_TO_REDUCE_COLOR)
    _draw_cells(active_reduced, ACTIVE_REDUCED_COLOR)
    _draw_cells(solved, SOLVED_COLOR)
    _draw_cells(mine, MINE_COLOR)
    _draw_cells(to_visualize, TO_VISUALIZE_COLOR)

    combined_img = Image.alpha_composite(base_image.convert("RGBA"), zone_overlay)

    # 2. Ajouter les actions du solver par-dessus (croix/ronds overlay_actions, sans fond de case)
    draw_actions = ImageDraw.Draw(combined_img)
    center_shift = cell_size // 2

    def _draw_action_symbol(act: SolverAction, px: int, py: int):
        """Dessine symbole blanc uniquement (croix pour SAFE/SWEEP/GUESS, rond pour FLAG)."""
        cx, cy = px + center_shift, py + center_shift
        size = max(6, cell_size // 3)
        
        if act.action == ActionType.SAFE:
            # Croix blanche pour SAFE/SWEEP
            draw_actions.line([cx - size, cy, cx + size, cy], fill=ACTION_SYMBOL_COLOR, width=2)
            draw_actions.line([cx, cy - size, cx, cy + size], fill=ACTION_SYMBOL_COLOR, width=2)
        elif act.action == ActionType.FLAG:
            # Rond blanc pour FLAG
            draw_actions.ellipse(
                [cx - size//2, cy - size//2, cx + size//2, cy + size//2],
                outline=ACTION_SYMBOL_COLOR,
                width=2,
            )
        elif act.action == ActionType.GUESS:
            # Croix blanche pour GUESS
            draw_actions.line([cx - size, cy, cx + size, cy], fill=ACTION_SYMBOL_COLOR, width=2)
            draw_actions.line([cx, cy - size, cx, cy + size], fill=ACTION_SYMBOL_COLOR, width=2)

    def _plot_actions(seq):
        for act in seq:
            if not act.coord or len(act.coord) != 2:
                continue
            # Si c'est un sweep, ne l'afficher que sur des cellules ACTIVE
            if act.action == ActionType.SAFE and "sweep" in (getattr(act, "reasoning", "") or "").lower():
                cell_for_action = cells.get(act.coord)
                if not cell_for_action or cell_for_action.solver_status != SolverStatus.ACTIVE:
                    continue
            cell_x, cell_y = act.coord
            px = (cell_x - start_x) * stride
            py = (cell_y - start_y) * stride
            _draw_action_symbol(act, px, py)

    _plot_actions(actions)
    if reducer_actions:
        _plot_actions(reducer_actions)

    return combined_img


def render_and_save_combined(
    base_image: Image.Image,
    cells: Dict[Coord, GridCell],
    actions: List[SolverAction],
    export_ctx: "ExportContext",
    bounds: Optional[Bounds] = None,
    stride: Optional[int] = None,
    reducer_actions: Optional[List[SolverAction]] = None,
) -> Optional[Path]:
    """Render et sauvegarde l'overlay combiné."""
    if not export_ctx.overlay_enabled:
        return None
    
    bounds = bounds or export_ctx.capture_bounds
    if bounds is None:
        return None
    
    stride = stride or export_ctx.capture_stride or (CELL_SIZE + CELL_BORDER)
    
    # Render optimisé avec filtrage des cellules pertinentes
    overlay_img = render_combined_overlay(
        base_image, cells, actions, bounds, stride,
        reducer_actions=reducer_actions
    )
    
    out_path = export_ctx.solver_overlay_path("s4c3_combined")
    # Optimisation PNG : compression et optimisation activées
    overlay_img.save(out_path, optimize=True, compress_level=6)
    
    # Export JSON associé
    _save_json(cells, actions, export_ctx, bounds, stride, reducer_actions)
    
    return out_path


def _save_json(
    cells: Dict[Coord, GridCell],
    actions: List[SolverAction],
    export_ctx: "ExportContext",
    bounds: Bounds,
    stride: int,
    reducer_actions: Optional[List[SolverAction]] = None,
) -> Optional[Path]:
    """Sauvegarde les métadonnées combinées en JSON."""
    # Optimisation : filtrer les cellules pertinentes (exclure UNREVEALED)
    relevant_statuses = {
        SolverStatus.ACTIVE,
        SolverStatus.FRONTIER,
        SolverStatus.SOLVED,
        SolverStatus.TO_VISUALIZE,
        SolverStatus.MINE,
    }
    
    # Compter les cellules par état
    counts = {
        "active_to_reduce": 0,
        "active_reduced": 0,
        "frontier_to_process": 0,
        "frontier_processed": 0,
        "solved": 0,
        "to_visualize": 0,
        "total_filtered": 0,  # Nombre de cellules filtrées (UNREVEALED)
    }
    
    # Liste des cellules pertinentes pour le JSON
    relevant_cells = []
    
    for cell in cells.values():
        if cell.solver_status not in relevant_statuses:
            counts["total_filtered"] += 1
            continue
            
        # Comptage
        if cell.solver_status == SolverStatus.ACTIVE:
            if cell.focus_level_active == ActiveRelevance.TO_REDUCE:
                counts["active_to_reduce"] += 1
            else:
                counts["active_reduced"] += 1
        elif cell.solver_status == SolverStatus.FRONTIER:
            if cell.focus_level_frontier == FrontierRelevance.TO_PROCESS:
                counts["frontier_to_process"] += 1
            else:
                counts["frontier_processed"] += 1
        elif cell.solver_status == SolverStatus.SOLVED:
            counts["solved"] += 1
        elif cell.solver_status == SolverStatus.TO_VISUALIZE:
            counts["to_visualize"] += 1
        
        # Ajouter à la liste des cellules pertinentes
        relevant_cells.append({
            "coord": cell.coord,
            "solver_status": cell.solver_status.name,
            "focus_level_active": cell.focus_level_active.name if cell.focus_level_active else None,
            "focus_level_frontier": cell.focus_level_frontier.name if cell.focus_level_frontier else None,
        })
    
    all_actions = list(actions) + (reducer_actions or [])
    
    payload = {
        "iteration": export_ctx.iteration,
        "game_id": export_ctx.game_id,
        "bounds": bounds,
        "stride": stride,
        "counts": counts,
        "action_count": len(all_actions),
        "relevant_cells_count": len(relevant_cells),
        "relevant_cells": relevant_cells,  # Cellules filtrées (max 1000)
        "actions": [
            {
                "coord": a.coord,
                "type": getattr(a.action, "name", str(a.action)),
                "reasoning": getattr(a, "reasoning", ""),
                "confidence": getattr(a, "confidence", None),
                "source": "reducer" if reducer_actions and a in reducer_actions else "main",
            }
            for a in all_actions
        ],
    }
    
    json_path = export_ctx.json_path("s4c3_combined", "combined")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    
    return json_path
