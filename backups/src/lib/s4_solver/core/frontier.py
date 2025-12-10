"""
Frontier - Calcul autonome de la frontière et des contraintes

Ce module calcule de manière autonome la frontière entre les zones connues
et inconnues, ainsi que les contraintes exercées par les chiffres sur les
cases inconnues.
"""

from typing import List, Dict, Set, Tuple
from lib.s3_solver.core.grid_state import GridState


class Frontier:
    """
    Représente la frontière entre le connu et l'inconnu.
    
    Calcule de manière autonome l'ensemble des cases inconnues adjacentes
    à au moins un chiffre, et maintient les contraintes associées.
    """
    
    def __init__(self, grid_state: GridState):
        """
        Construit la frontière à partir d'un GridState.
        
        Args:
            grid_state: État normalisé de la grille
        """
        self.grid_state = grid_state
        self.cells: Set[Tuple[int, int]] = set()  # Cases de la frontière
        self.constraints: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}  # Case -> Chiffres contraignants
        
        self._build()
    
    def _build(self):
        """Construit la frontière et les contraintes inverses"""
        # Parcourir toutes les cellules pour trouver les chiffres
        all_cells = self.grid_state.get_all_cells()
        
        for (x, y), val in all_cells.items():
            if 0 <= val <= 8:  # C'est un chiffre
                # Vérifier s'il a des voisins inconnus
                unknown_neighbors = self._get_unknown_neighbors(x, y)
                
                if unknown_neighbors:
                    # Pour chaque voisin inconnu, l'ajouter à la frontière
                    # et noter que ce chiffre exerce une contrainte dessus
                    for ux, uy in unknown_neighbors:
                        self.cells.add((ux, uy))
                        
                        if (ux, uy) not in self.constraints:
                            self.constraints[(ux, uy)] = []
                        
                        self.constraints[(ux, uy)].append((x, y))
    
    def _get_unknown_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Retourne les voisins inconnus d'une case"""
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                nx, ny = x + dx, y + dy
                if self.grid_state.get_cell(nx, ny) == GridState.UNKNOWN:
                    neighbors.append((nx, ny))
        
        return neighbors
    
    def get_frontier_cells(self) -> Set[Tuple[int, int]]:
        """Retourne l'ensemble des cases de la frontière"""
        return self.cells.copy()
    
    def get_constraints_for_cell(self, x: int, y: int) -> List[Tuple[int, int]]:
        """
        Retourne la liste des coordonnées des chiffres qui contraignent cette case inconnue.
        
        Args:
            x, y: Coordonnées de la case inconnue
            
        Returns:
            Liste des coordonnées des chiffres voisins
        """
        return self.constraints.get((x, y), [])
    
    def get_constraint_value(self, x: int, y: int) -> int:
        """
        Retourne la valeur de la contrainte (nombre de mines) pour une case de chiffre.
        
        Args:
            x, y: Coordonnées de la case de chiffre
            
        Returns:
            Valeur du chiffre (nombre de mines adjacentes)
        """
        return self.grid_state.get_cell(x, y) or 0
    
    def get_cells_constrained_by(self, x: int, y: int) -> List[Tuple[int, int]]:
        """
        Retourne la liste des cases inconnues contraintes par un chiffre donné.
        
        Args:
            x, y: Coordonnées du chiffre
            
        Returns:
            Liste des cases inconnues adjacentes à ce chiffre
        """
        return self._get_unknown_neighbors(x, y)
    
    def size(self) -> int:
        """Retourne le nombre de cases dans la frontière"""
        return len(self.cells)
    
    def is_empty(self) -> bool:
        """Vérifie si la frontière est vide"""
        return len(self.cells) == 0
