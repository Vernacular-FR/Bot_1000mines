from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw

from src.lib.s4_solver.facade import SolverAction, SolverActionType
from src.lib.s3_storage.facade import LogicalCellState


def render_combined_overlay(
    screenshot_path: Path,
    bounds: Tuple[int, int, int, int],
    actions: List[SolverAction],
    zones: Tuple[set, set, set],  # (active, frontier, solved)
    cells: dict,  # Ajout des cellules pour calculer effective values
    stride: int,
    cell_size: int,
    output_dir: Path,
) -> Path:
    """
    Génère un overlay combiné avec zones mises à jour + actions du solver.
    
    Les cellules actives deviennent 'solved' quand toutes leurs voisines sont résolues.
    """
    from ..s40_grid_analyzer.zone_overlay import render_zone_overlay
    
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
    
    # 1. Générer l'overlay des zones (fond) - AVEC ZONES MISES À JOUR
    print(f"[DEBUG COMBINED] Génération zone_overlay avec bounds={bounds}")
    zone_overlay_path = render_zone_overlay(
        screenshot_path,
        bounds,
        active=updated_active,  # ✅ Utiliser les zones mises à jour
        frontier=frontier,
        solved=updated_solved,  # ✅ Utiliser les zones mises à jour
        stride=stride,
        cell_size=cell_size,
        output_dir=output_dir.parent / "temp_zones",
    )
    print(f"[DEBUG COMBINED] Zone overlay généré: {zone_overlay_path}")
    
    # 2. Ouvrir l'image de base et l'overlay des zones
    base_img = Image.open(screenshot_path)
    zone_img = Image.open(zone_overlay_path)
    
    # 3. Créer l'image combinée
    combined_img = Image.new('RGBA', base_img.size)
    combined_img.paste(base_img)
    combined_img.paste(zone_img, (0, 0), zone_img)  # Utiliser alpha channel
    
    # 4. Ajouter les actions du solver par-dessus (sans transparence)
    draw = ImageDraw.Draw(combined_img)
    
    start_x, start_y, _, _ = bounds
    
    # Importer et utiliser la fonction centralisée pour dessiner les actions
    from .actions_overlay import draw_action_on_image
    
    for action in actions:
        if not action.cell or len(action.cell) != 2:
            continue
            
        cell_x, cell_y = action.cell
        
        # COORDONNÉES CORRECTES : soustraire start_x/start_y avant de multiplier
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        
        # Utiliser la fonction centralisée pour dessiner l'action
        draw_action_on_image(draw, action, px, py, cell_size)
    
    # 5. Sauvegarder l'image combinée
    output_dir.mkdir(exist_ok=True, parents=True)
    output_path = output_dir / f"{screenshot_path.stem}_combined_solver.png"
    combined_img.save(output_path)
    
    # 6. Nettoyer le fichier temporaire
    zone_overlay_path.unlink(missing_ok=True)
    try:
        zone_overlay_path.parent.rmdir()
    except OSError:
        pass  # Le dossier n'est pas vide ou n'existe pas
    
    return output_path
