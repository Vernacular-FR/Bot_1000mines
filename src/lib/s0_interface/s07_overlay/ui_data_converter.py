"""
Convertisseur de données solver/storage vers format UI overlay.
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from .ui_controller import StatusCellData, ActionCellData, ProbabilityCellData


def convert_snapshot_to_status(
    snapshot: Dict[Tuple[int, int], any],
    bounds_offset: Optional[Tuple[int, int]] = None,
) -> List[StatusCellData]:
    """
    Convertit un snapshot storage en données pour l'overlay status.
    
    Args:
        snapshot: Dictionnaire {(col, row): GridCell}
        bounds_offset: Offset (min_col, min_row) pour coordonnées relatives
        
    Returns:
        Liste de StatusCellData pour l'overlay
    """
    offset_col, offset_row = bounds_offset or (0, 0)
    cells = []
    
    for (col, row), cell in snapshot.items():
        # Convertir en coordonnées relatives à l'overlay
        rel_col = col - offset_col
        rel_row = row - offset_row
        
        # Déterminer le statut à afficher
        status = cell.solver_status.name if hasattr(cell.solver_status, 'name') else str(cell.solver_status)
        
        # Mapper vers les noms attendus par l'UI
        status_map = {
            'UNREVEALED': 'UNREVEALED',
            'ACTIVE': 'ACTIVE',
            'FRONTIER': 'FRONTIER',
            'SOLVED': 'SOLVED',
            'MINE': 'MINE',
            'TO_VISUALIZE': 'TO_VISUALIZE',
            'JUST_VISUALIZED': 'TO_VISUALIZE',
        }
        ui_status = status_map.get(status, 'UNREVEALED')
        
        cells.append(StatusCellData(
            col=rel_col,
            row=rel_row,
            status=ui_status,
        ))
    
    return cells


def convert_actions_to_overlay(
    actions: List[any],
    bounds_offset: Optional[Tuple[int, int]] = None,
) -> List[ActionCellData]:
    """
    Convertit des actions solver en données pour l'overlay actions.
    
    Args:
        actions: Liste de SolverAction
        bounds_offset: Offset (min_col, min_row) pour coordonnées relatives
        
    Returns:
        Liste de ActionCellData pour l'overlay
    """
    offset_col, offset_row = bounds_offset or (0, 0)
    result = []
    
    for action in actions:
        col, row = action.coord
        rel_col = col - offset_col
        rel_row = row - offset_row
        
        # Mapper le type d'action
        action_type = action.action.name if hasattr(action.action, 'name') else str(action.action)
        
        result.append(ActionCellData(
            col=rel_col,
            row=rel_row,
            type=action_type,
            confidence=getattr(action, 'confidence', 1.0),
        ))
    
    return result


def convert_probabilities_to_overlay(
    zone_probabilities: Dict[int, float],
    zones: List[any],
    bounds_offset: Optional[Tuple[int, int]] = None,
) -> List[ProbabilityCellData]:
    """
    Convertit les probabilités CSP en données pour l'overlay probas.
    
    Args:
        zone_probabilities: Dict {zone_id: probability}
        zones: Liste des zones avec leurs cellules
        bounds_offset: Offset (min_col, min_row) pour coordonnées relatives
        
    Returns:
        Liste de ProbabilityCellData pour l'overlay
    """
    offset_col, offset_row = bounds_offset or (0, 0)
    result = []
    
    for zone in zones:
        prob = zone_probabilities.get(zone.id, 0.5)
        
        for col, row in zone.cells:
            rel_col = col - offset_col
            rel_row = row - offset_row
            
            result.append(ProbabilityCellData(
                col=rel_col,
                row=rel_row,
                probability=prob,
            ))
    
    return result


def filter_visible_cells(
    cells: List[any],
    visible_bounds: Tuple[int, int, int, int],
) -> List[any]:
    """
    Filtre les cellules pour ne garder que celles visibles à l'écran.
    
    Args:
        cells: Liste de cellules (StatusCellData, ActionCellData, etc.)
        visible_bounds: (min_col, min_row, max_col, max_row) visibles
        
    Returns:
        Liste filtrée
    """
    min_col, min_row, max_col, max_row = visible_bounds
    
    return [
        c for c in cells
        if min_col <= c.col <= max_col and min_row <= c.row <= max_row
    ]
