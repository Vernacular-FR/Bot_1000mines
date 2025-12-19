"""Logique d'exploration risquée pour le planner."""

import random
from typing import Dict, List, Optional, Set
from src.lib.s3_storage.types import Coord, GridCell, LogicalCellState, SolverStatus
from src.lib.s4_solver.types import SolverAction, ActionType
from src.config import EXPLORATION_CONFIG

def find_exploration_candidates(
    snapshot: Dict[Coord, GridCell],
    min_distance: int = EXPLORATION_CONFIG['distance_min'],
    max_distance: int = EXPLORATION_CONFIG['distance_max']
) -> List[Coord]:
    """Identifie les cellules UNREVEALED à une distance raisonnable de la frontière.
    
    Une cellule est candidate si elle est UNREVEALED et que sa distance Chebyshev 
    minimale par rapport à la zone active est comprise entre min_distance et max_distance.
    """
    # 1. Identifier la zone active (frontière et cellules actives)
    active_coords: List[Coord] = [
        coord for coord, cell in snapshot.items()
        if cell.solver_status in (SolverStatus.ACTIVE, SolverStatus.FRONTIER)
    ]
    
    if not active_coords:
        # Si pas de frontière (début de partie), on prend des cases proches du centre (0,0)
        unrevealed = [c for c, cell in snapshot.items() if cell.logical_state == LogicalCellState.UNREVEALED]
        return [c for c in unrevealed if abs(c[0]) < 15 and abs(c[1]) < 15]

    # 2. Identifier toutes les UNREVEALED
    unrevealed = [c for c, cell in snapshot.items() if cell.logical_state == LogicalCellState.UNREVEALED]
    
    # 3. Filtrer par plage de distance
    candidates = []
    for ux, uy in unrevealed:
        min_dist_found = 999999
        for ax, ay in active_coords:
            dist = max(abs(ux - ax), abs(uy - ay))
            if dist < min_dist_found:
                min_dist_found = dist
            if min_dist_found < min_distance:
                break
        
        if min_distance <= min_dist_found <= max_distance:
            candidates.append((ux, uy))
            
    return candidates

def select_exploration_action(candidates: List[Coord]) -> Optional[SolverAction]:
    """Choisit une action d'exploration parmi les candidats."""
    if not candidates:
        return None
        
    target = random.choice(candidates)
    
    return SolverAction(
        coord=target,
        action=ActionType.GUESS,
        confidence=0.5,
        reasoning=f"Exploration risquée (distance > 10 de la frontière)"
    )
