"""
StatusClassifier – Classification unique des cellules pour le solver.

Remplace StateManager et FrontierClassifier (duplication éliminée).
Gère la classification initiale et l'assignation des focus levels.
"""

from typing import Dict, Set, Tuple
from dataclasses import replace

from src.lib.s3_storage.facade import (
    StorageUpsert,
    GridCell,
    Coord,
    SolverStatus,
    ActiveRelevance,
    FrontierRelevance,
    LogicalCellState,
)


class StatusClassifier:
    """
    Classification unique des cellules avec focus assignment.
    - ACTIVE : nombres avec voisins non révélés
    - FRONTIER : non révélées voisines d'ACTIVE
    - SOLVED : nombres sans voisins non révélés, vides, mines confirmées
    - JUST_VISUALIZED : autres cellules révélées par la vision
    """
    
    @staticmethod
    def classify_grid(cells_snapshot: Dict[Coord, GridCell]) -> StorageUpsert:
        """
        Classification initiale basée sur logical_state.
        Initialise les focus : ACTIVE→TO_REDUCE, FRONTIER→TO_PROCESS
        
        Args:
            cells_snapshot: Snapshot actuel des cellules depuis Storage
            
        Returns:
            StorageUpsert avec les cellules modifiées
        """
        updated_cells: Dict[Coord, GridCell] = {}
        
        # Étape 1: Identifier ACTIVE et SOLVED
        active: Set[Coord] = set()
        solved: Set[Coord] = set()
        
        for coord, cell in cells_snapshot.items():
            if cell.logical_state == LogicalCellState.OPEN_NUMBER and cell.number_value is not None:
                if StatusClassifier._has_unrevealed_neighbor(coord, cells_snapshot):
                    active.add(coord)
                else:
                    solved.add(coord)
            elif cell.logical_state in (LogicalCellState.EMPTY, LogicalCellState.CONFIRMED_MINE):
                solved.add(coord)
        
        # Étape 2: Identifier FRONTIER (non révélées voisines d'ACTIVE)
        frontier: Set[Coord] = set()
        for coord, cell in cells_snapshot.items():
            if cell.logical_state == LogicalCellState.UNREVEALED:
                if StatusClassifier._has_active_neighbor(coord, active, cells_snapshot):
                    frontier.add(coord)
        
        # Étape 3: Construire les cellules mises à jour avec solver_status et focus
        for coord, cell in cells_snapshot.items():
            new_cell = cell
            
            # Ne traiter que les cellules JUST_VISUALIZED (qui viennent d'être révélées par la vision)
            if cell.solver_status == SolverStatus.JUST_VISUALIZED:
                if coord in active:
                    new_cell = replace(
                        cell,
                        solver_status=SolverStatus.ACTIVE,
                        focus_level_active=ActiveRelevance.TO_REDUCE,
                        focus_level_frontier=None,
                    )
                elif coord in frontier:
                    new_cell = replace(
                        cell,
                        solver_status=SolverStatus.FRONTIER,
                        focus_level_active=None,
                        focus_level_frontier=FrontierRelevance.TO_PROCESS,
                    )
                elif coord in solved:
                    new_cell = replace(
                        cell,
                        solver_status=SolverStatus.SOLVED,
                        focus_level_active=None,
                        focus_level_frontier=None,
                    )
                # Les autres JUST_VISUALIZED restent JUST_VISUALIZED (cas rares)
                
                if new_cell != cell:
                    updated_cells[coord] = new_cell
        
        return StorageUpsert(
            cells=updated_cells,
            active_remove=set(),
            frontier_add=set(),
            frontier_remove=set(),
            to_visualize=set(),
        )
    
    @staticmethod
    def _has_unrevealed_neighbor(coord: Coord, cells: Dict[Coord, GridCell]) -> bool:
        """Vérifie si une cellule a des voisins non révélés."""
        for nb in StatusClassifier._neighbors(coord):
            neighbor = cells.get(nb)
            if neighbor and neighbor.logical_state == LogicalCellState.UNREVEALED:
                return True
        return False
    
    @staticmethod
    def _has_active_neighbor(coord: Coord, active: Set[Coord], cells: Dict[Coord, GridCell]) -> bool:
        """Vérifie si une cellule non révélée est voisine d'une ACTIVE."""
        for nb in StatusClassifier._neighbors(coord):
            if nb in active:
                return True
        return False
    
    @staticmethod
    def _neighbors(coord: Coord) -> Set[Coord]:
        """Retourne les 8 voisins d'une coordonnée."""
        x, y = coord
        return {
            (x-1, y-1), (x, y-1), (x+1, y-1),
            (x-1, y),             (x+1, y),
            (x-1, y+1), (x, y+1), (x+1, y+1)
        }
