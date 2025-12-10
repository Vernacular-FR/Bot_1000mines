"""
GridAnalyzer - Orchestrateur d'analyse de grille

Ce module combine GridState et Frontier pour fournir une interface
unifiée d'analyse de grille pour les autres modules du solveur.
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from src.lib.s3_tensor.grid_state import GamePersistence, GridDB
from src.lib.s4_solver.core.grid_state import GridState
from src.lib.s4_solver.core.frontier import Frontier


class GridAnalyzer:
    """
    Orchestrateur qui combine GridState et Frontier pour l'analyse complète.
    
    Fournit une interface simple pour accéder aux données de la grille
    et à la frontière, tout en gardant les responsabilités bien séparées.
    """
    
    def __init__(self, db: Optional[GridDB] = None, *, tensor_view: Optional[Dict[str, Any]] = None):
        """
        Initialise l'analyseur avec une base de données.
        
        Args:
            db: Base de données GridDB contenant l'état de la grille
        """
        self.grid_state = GridState(db, tensor_view=tensor_view)
        self.frontier = Frontier(self.grid_state)
    
    # Délégation vers GridState
    def get_cell(self, x: int, y: int) -> Optional[int]:
        """Retourne la valeur d'une cellule"""
        return self.grid_state.get_cell(x, y)
    
    def get_all_cells(self) -> Dict[Tuple[int, int], int]:
        """Retourne toutes les cellules"""
        return self.grid_state.get_all_cells()
    
    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Retourne les bornes de la grille"""
        return self.grid_state.get_bounds()
    
    def get_cells_by_type(self, value: int) -> Dict[Tuple[int, int], int]:
        """Retourne les cellules d'un type donné"""
        return self.grid_state.get_cells_by_type(value)
    
    def get_number_cells(self) -> Dict[Tuple[int, int], int]:
        """Retourne toutes les cases avec des chiffres"""
        return {pos: val for pos, val in self.grid_state.get_all_cells().items() 
                if 1 <= val <= 8}
    
    def get_unknown_cells(self) -> Dict[Tuple[int, int], int]:
        """Retourne toutes les cases inconnues"""
        return self.grid_state.get_cells_by_type(GridState.UNKNOWN)
    
    # Délégation vers Frontier
    def get_frontier_cells(self) -> Set[Tuple[int, int]]:
        """Retourne les cases de la frontière"""
        return self.frontier.get_frontier_cells()
    
    def get_constraints_for_cell(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Retourne les contraintes pour une case inconnue"""
        return self.frontier.get_constraints_for_cell(x, y)
    
    def get_constraint_value(self, x: int, y: int) -> int:
        """Retourne la valeur d'une contrainte (chiffre)"""
        return self.frontier.get_constraint_value(x, y)
    
    def get_cells_constrained_by(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Retourne les cases inconnues contraintes par un chiffre"""
        return self.frontier.get_cells_constrained_by(x, y)
    
    def frontier_size(self) -> int:
        """Retourne la taille de la frontière"""
        return self.frontier.size()
    
    def is_frontier_empty(self) -> bool:
        """Vérifie si la frontière est vide"""
        return self.frontier.is_empty()
    
    # Méthodes combinées pratiques
    def get_frontier_with_constraints(self) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
        """Retourne un dictionnaire case -> contraintes pour toute la frontière"""
        result = {}
        for cell in self.frontier.get_frontier_cells():
            result[cell] = self.frontier.get_constraints_for_cell(*cell)
        return result
    
    def get_constraint_groups(self) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
        """
        Retourne les groupes de contraintes: chiffre -> cases inconnues associées.
        Utile pour la segmentation.
        """
        groups = {}
        for cell in self.frontier.get_frontier_cells():
            constraints = self.frontier.get_constraints_for_cell(*cell)
            for constraint_cell in constraints:
                if constraint_cell not in groups:
                    groups[constraint_cell] = []
                groups[constraint_cell].append(cell)
        return groups
    
    # Constantes
    @property
    def UNKNOWN(self) -> int:
        return GridState.UNKNOWN
    
    @property
    def FLAG(self) -> int:
        return GridState.FLAG
    
    @property
    def SAFE(self) -> int:
        return GridState.SAFE
