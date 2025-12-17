from __future__ import annotations

from pathlib import Path
import sys
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw

from src.lib.s1_capture.s10_overlay_utils import build_overlay_metadata_from_session
from src.lib.s3_storage.facade import (
    ActiveRelevance,
    FrontierRelevance,
    GridCell,
    LogicalCellState,
    SolverStatus,
)
from src.lib.s4_solver.facade import SolverAction, SolverActionType
from .s495_historical_canvas import build_historical_canvas_from_canvas, _parse_canvas_name

ACTIVE_TO_REDUCE_COLOR = (0, 120, 255, 200)
ACTIVE_REDUCED_COLOR = (0, 120, 255, 90)
FRONTIER_TO_PROCESS_COLOR = (255, 200, 0, 200)
FRONTIER_PROCESSED_COLOR = (255, 200, 0, 90)
SOLVED_COLOR = (0, 180, 90, 90)
TOVIZ_COLOR = (0, 0, 0, 200)


def render_combined_overlay(
    screenshot_path: Optional[Path],
    bounds: Optional[Tuple[int, int, int, int]],
    actions: List[SolverAction],
    zones: Tuple[set, set, set],  # conservé pour compat, mais l'état provient de cells
    cells: Dict[Tuple[int, int], GridCell],
    stride: Optional[int],
    cell_size: Optional[int],
    export_root: Optional[Path],
    reducer_actions: List[SolverAction] | None = None,
) -> Optional[Path]:
    """
    Génère un overlay combiné avec zones mises à jour + actions du solver.
    
    Les cellules actives deviennent 'solved' quand toutes leurs voisines sont résolues.
    """
    meta = None
    if not (screenshot_path and bounds and stride and cell_size and export_root):
        meta = build_overlay_metadata_from_session()
        if not meta:
            return None
        screenshot_path = Path(meta["screenshot_path"])
        bounds = meta["bounds"]
        stride = meta["stride"]
        cell_size = meta["cell_size"]
        export_root = Path(meta["export_root"])
    else:
        meta = build_overlay_metadata_from_session()

    # Fond et bounds via canvas historique
    if meta:
        current_canvas = Path(meta["screenshot_path"])
        hist_path = build_historical_canvas_from_canvas(current_canvas, Path(meta["export_root"]))
        if hist_path and hist_path.exists():
            screenshot_path = hist_path
            parsed = _parse_canvas_name(hist_path)
            if parsed:
                _, _, bounds = parsed

    # 0. Reconstituer les zones depuis cells (et valider les focus)
    active_to_reduce: set[Tuple[int, int]] = set()
    active_reduced: set[Tuple[int, int]] = set()
    frontier_to_process: set[Tuple[int, int]] = set()
    frontier_processed: set[Tuple[int, int]] = set()
    solved: set[Tuple[int, int]] = set()
    to_visualize: set[Tuple[int, int]] = set()

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

    updated_active = active_to_reduce | active_reduced
    updated_solved = set(solved)
    initial_active_count = len(updated_active)
    initial_solved_count = len(updated_solved)
    
    # Simuler les états des actions trouvées
    simulated_states = {}
    for action in actions:
        if action.type == SolverActionType.CLICK:
            simulated_states[action.cell] = LogicalCellState.EMPTY
            if "cleanup" not in (getattr(action, "reasoning", "") or "").lower():
                to_visualize.add(action.cell)
        elif action.type == SolverActionType.FLAG:
            simulated_states[action.cell] = LogicalCellState.CONFIRMED_MINE
    if reducer_actions:
        for action in reducer_actions:
            if action.type == SolverActionType.CLICK:
                simulated_states[action.cell] = LogicalCellState.EMPTY
                to_visualize.add(action.cell)
            elif action.type == SolverActionType.FLAG:
                simulated_states[action.cell] = LogicalCellState.CONFIRMED_MINE
    
    # Vérifier chaque cellule active : si effective_value == 0, elle devient solved
    for cell_coord in list(updated_active):
        if cell_coord in cells:
            cell = cells[cell_coord]
            if cell.logical_state == LogicalCellState.OPEN_NUMBER and cell.number_value is not None:
                # Compter les mines confirmées autour de cette cellule
                neighbor_mines = 0
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = cell_coord[0] + dx, cell_coord[1] + dy
                        neighbor_coord = (nx, ny)
                        if neighbor_coord in simulated_states:
                            if simulated_states[neighbor_coord] == LogicalCellState.CONFIRMED_MINE:
                                neighbor_mines += 1
                        elif neighbor_coord in cells and cells[neighbor_coord].logical_state == LogicalCellState.CONFIRMED_MINE:
                            neighbor_mines += 1
                
                # Effective value = nombre - mines confirmées
                effective_value = cell.number_value - neighbor_mines
                
                # Si effective_value == 0, toutes les voisines sont résolues -> cellule devient solved
                if effective_value == 0:
                    updated_active.discard(cell_coord)
                    updated_solved.add(cell_coord)
    
    print(
        f"[DEBUG COMBINED] Zones mises à jour: "
        f"active={initial_active_count}->{len(updated_active)}, "
        f"solved={initial_solved_count}->{len(updated_solved)}"
    )
    
    # 1. Overlay zones en mémoire (pas de fichier intermédiaire)
    print(f"[DEBUG COMBINED] Génération overlay zones en mémoire avec bounds={bounds}")
    base_img = Image.open(screenshot_path).convert("RGBA")
    zone_overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
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

    # Découper updated_active en to_reduce / reduced pour le rendu
    active_to_reduce_draw = {c for c in updated_active if c in active_to_reduce}
    active_reduced_draw = updated_active - active_to_reduce_draw

    _draw_cells(frontier_to_process, FRONTIER_TO_PROCESS_COLOR)
    _draw_cells(frontier_processed, FRONTIER_PROCESSED_COLOR)
    _draw_cells(active_to_reduce_draw, ACTIVE_TO_REDUCE_COLOR)
    _draw_cells(active_reduced_draw, ACTIVE_REDUCED_COLOR)
    _draw_cells(updated_solved, SOLVED_COLOR)
    _draw_cells(to_visualize, TOVIZ_COLOR)

    combined_img = Image.alpha_composite(base_img, zone_overlay)

    # 2. Ajouter les actions du solver par-dessus (croix/ronds uniquement, sans remplissage)
    draw_actions = ImageDraw.Draw(combined_img)
    margin = 2
    center_shift = cell_size // 2

    def _draw_action_symbol(act: SolverAction, px: int, py: int):
        cx, cy = px + center_shift, py + center_shift
        size = max(6, cell_size // 3)
        if act.type == SolverActionType.CLICK:
            draw_actions.line([cx - size, cy, cx + size, cy], fill=(255, 255, 255, 255), width=3)
            draw_actions.line([cx, cy - size, cx, cy + size], fill=(255, 255, 255, 255), width=3)
        elif act.type == SolverActionType.FLAG:
            draw_actions.ellipse(
                [cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2],
                outline=(255, 255, 255, 255),
                width=3,
            )
        elif act.type == SolverActionType.GUESS:
            draw_actions.line([cx - size, cy, cx + size, cy], fill=(255, 255, 0, 255), width=3)
            draw_actions.line([cx, cy - size, cx, cy + size], fill=(255, 255, 0, 255), width=3)

    def _plot_actions(seq):
        for act in seq:
            if not act.cell or len(act.cell) != 2:
                continue
            cell_x, cell_y = act.cell
            px = (cell_x - start_x) * stride
            py = (cell_y - start_y) * stride
            _draw_action_symbol(act, px, py)

    _plot_actions(actions)
    if reducer_actions:
        _plot_actions(reducer_actions)

    # 3. Sauvegarder l'image combinée
    out_dir = Path(export_root) / "s4_solver/s43_csp_combined_overlay"
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = out_dir / f"{screenshot_path.stem}_combined_solver.png"
    combined_img.save(overlay_path)

    # JSON log
    try:
        json_dir = out_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "bounds": bounds,
            "stride": stride,
            "cell_size": cell_size,
            "actions": [
                {
                    "cell": a.cell,
                    "type": getattr(a.type, "name", str(a.type)),
                    "reasoning": getattr(a, "reasoning", ""),
                    "confidence": getattr(a, "confidence", None),
                    "source": "reducer" if reducer_actions and a in reducer_actions else "csp_or_cleanup",
                }
                for a in list(actions) + (reducer_actions or [])
            ],
            "counts": {
                "active_to_reduce": len(active_to_reduce_draw),
                "active_reduced": len(active_reduced_draw),
                "frontier_to_process": len(frontier_to_process),
                "frontier_processed": len(frontier_processed),
                "solved": len(updated_solved),
                "to_visualize": len(to_visualize),
            },
        }
        import json

        json_path = json_dir / f"{screenshot_path.stem}_combined_solver.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return overlay_path
