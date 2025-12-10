"""
GridState - Extraction et normalisation des données de la grille

Ce module extrait les données brutes de GridDB et les normalise pour les autres
modules du solveur. Il ne fait aucune analyse, seulement de l'extraction.
"""

from typing import Dict, Tuple, Optional
from src.lib.s3_tensor.grid_state import GamePersistence, GridDB


class GridState:
    """
    Représentation immuable des données extraites de GridDB.
    
    Fournit une interface simple et normalisée pour accéder aux états
    des cellules sans dépendre directement de GridDB.
    """
    
    # Constantes d'état (alignées avec l'ancienne classe Grid)
    UNKNOWN = -1
    FLAG = -2
    SAFE = -3  # Marqueur temporaire pour les cases déduites sûres
    
    def __init__(self, db: GridDB):
        """Extrait et normalise les données depuis GridDB"""
        self.cells: Dict[Tuple[int, int], int] = {}
        self.width = 0
        self.height = 0
        
        self._extract_from_db(db)
    
    def _extract_from_db(self, db: GridDB):
        """Extrait les données brutes de GridDB"""
        # Extraire les dimensions
        bounds = db.get_bounds()
        if bounds:
            self.width = bounds[2] - bounds[0] + 1
            self.height = bounds[3] - bounds[1] + 1
        
        # Extraire toutes les cellules
        all_cells = db.get_all_cells()
        for cell_data in all_cells:
            x = cell_data['x']
            y = cell_data['y']
            cell_type = cell_data['type']
            
            # Convertir les types en valeurs numériques
            value = self._convert_type_to_value(cell_type)
            self.cells[(x, y)] = value
    
    def _convert_type_to_value(self, cell_type: str) -> int:
        """Convertit le type de cellule en valeur numérique"""
        if cell_type.startswith('number_'):
            return int(cell_type.split('_')[1])
        elif cell_type == 'empty':
            return 0
        elif cell_type == 'unknown':
            return self.UNKNOWN
        elif cell_type == 'flag':
            return self.FLAG
        else:
            return self.UNKNOWN
    
    def get_cell(self, x: int, y: int) -> Optional[int]:
        """Retourne la valeur d'une cellule ou None si hors grille"""
        return self.cells.get((x, y))
    
    def get_all_cells(self) -> Dict[Tuple[int, int], int]:
        """Retourne toutes les cellules"""
        return self.cells.copy()
    
    def get_cells_by_type(self, value: int) -> Dict[Tuple[int, int], int]:
        """Retourne toutes les cellules d'un type donné"""
        return {pos: val for pos, val in self.cells.items() if val == value}
    
    def get_bounds(self) -> Tuple[int, int, int, int]:
        """Retourne les bornes (min_x, min_y, max_x, max_y)"""
        if not self.cells:
            return (0, 0, 0, 0)
        
        xs = [x for x, y in self.cells.keys()]
        ys = [y for x, y in self.cells.keys()]
        return (min(xs), min(ys), max(xs), max(ys))
    
    def is_in_bounds(self, x: int, y: int) -> bool:
        """Vérifie si une coordonnée est dans les bornes de la grille"""
        return (x, y) in self.cells
