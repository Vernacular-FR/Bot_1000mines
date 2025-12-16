from __future__ import annotations

from pathlib import Path
import sys
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw

from src.lib.s1_capture.s10_overlay_utils import build_overlay_metadata_from_session
from src.lib.s3_storage.facade import LogicalCellState
from src.lib.s4_solver.facade import SolverAction, SolverActionType

ACTIVE_COLOR = (0, 120, 255, 180)
FRONTIER_COLOR = (255, 170, 0, 200)
SOLVED_COLOR = (0, 180, 90, 180)


def render_combined_overlay(
    screenshot_path: Optional[Path],
    bounds: Optional[Tuple[int, int, int, int]],
    actions: List[SolverAction],
    zones: Tuple[set, set, set],  # (active, frontier, solved)
    cells: dict,  # Ajouter les cellules pour calculer effective values
    stride: Optional[int],
    cell_size: Optional[int],
    export_root: Optional[Path],
    reducer_actions: List[SolverAction] | None = None,
) -> Optional[Path]:
    """
    Génère un overlay combiné avec zones mises à jour + actions du solver.
    
    Les cellules actives deviennent 'solved' quand toutes leurs voisines sont résolues.
    """
    if not (screenshot_path and bounds and stride and cell_size and export_root):
        meta = build_overlay_metadata_from_session()
        if not meta:
            return None
        screenshot_path = Path(meta["screenshot_path"])
        bounds = meta["bounds"]
        stride = meta["stride"]
        cell_size = meta["cell_size"]
        export_root = Path(meta["export_root"])

    active, frontier, solved = zones
    
    # 0. Mettre à jour les zones : active -> solved quand toutes les voisines sont résolues
    updated_active = set(active)
    updated_solved = set(solved)
    
    # Simuler les états des actions trouvées
    simulated_states = {}
    for action in actions:
        if action.type == SolverActionType.CLICK:
            simulated_states[action.cell] = LogicalCellState.EMPTY
        elif action.type == SolverActionType.FLAG:
            simulated_states[action.cell] = LogicalCellState.CONFIRMED_MINE
    if reducer_actions:
        for action in reducer_actions:
            if action.type == SolverActionType.CLICK:
                simulated_states[action.cell] = LogicalCellState.EMPTY
            elif action.type == SolverActionType.FLAG:
                simulated_states[action.cell] = LogicalCellState.CONFIRMED_MINE
    
    # Vérifier chaque cellule active : si effective_value == 0, elle devient solved
    for cell_coord in active:
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
                    updated_active.remove(cell_coord)
                    updated_solved.add(cell_coord)
    
    print(f"[DEBUG COMBINED] Zones mises à jour: active={len(active)}->{len(updated_active)}, solved={len(solved)}->{len(updated_solved)}")
    
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

    _draw_cells(updated_active, ACTIVE_COLOR)
    _draw_cells(frontier, FRONTIER_COLOR)
    _draw_cells(updated_solved, SOLVED_COLOR)

    combined_img = Image.alpha_composite(base_img, zone_overlay)

    # 2. Ajouter les actions du solver par-dessus
    draw_actions = ImageDraw.Draw(combined_img)
    from .s493_actions_overlay import draw_action_on_image

    for action in actions:
        if not action.cell or len(action.cell) != 2:
            continue
        cell_x, cell_y = action.cell
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw_actions, action, px, py, cell_size)
    if reducer_actions:
        for action in reducer_actions:
            if not action.cell or len(action.cell) != 2:
                continue
            cell_x, cell_y = action.cell
            px = (cell_x - start_x) * stride
            py = (cell_y - start_y) * stride
            draw_action_on_image(draw_actions, action, px, py, cell_size, opacity=255)

    # 3. Sauvegarder l'image combinée
    out_dir = Path(export_root) / "s43_csp_combined_overlay"
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = out_dir / f"{screenshot_path.stem}_combined_solver.png"
    combined_img.save(overlay_path)
    return overlay_path
