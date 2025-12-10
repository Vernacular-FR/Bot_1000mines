"""
GridState - Extraction et normalisation des données de la grille

Ce module extrait les données brutes de GridDB et les normalise pour les autres
modules du solveur. Il ne fait aucune analyse, seulement de l'extraction.
"""

from typing import Dict, Tuple, Optional, Any
from src.lib.s3_tensor.grid_state import GamePersistence, GridDB
from src.lib.s3_tensor.tensor_grid import TensorGrid
from src.lib.s3_tensor.types import CellType


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
    
    def __init__(self, db: Optional[GridDB] = None, *, tensor_view: Optional[Dict[str, Any]] = None):
        """Extrait et normalise les données depuis GridDB"""
        self.cells: Dict[Tuple[int, int], int] = {}
        self.width = 0
        self.height = 0
        self.bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)
        self._frontier_hint: Optional[Set[Tuple[int, int]]] = None

        if tensor_view is not None:
            self._extract_from_tensor_view(tensor_view)
        elif db is not None:
            self._extract_from_db(db)
        else:
            raise ValueError("GridState requires either a GridDB or a tensor_view")
    
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
            self._update_bounds(x, y)

    def _extract_from_tensor_view(self, view: Dict[str, Any]):
        """Extrait les données à partir d'une vue TensorGrid."""
        values = view["values"]
        frontier_mask = view.get("frontier_mask")
        origin_x, origin_y = view.get("origin", (0, 0))
        bounds = view.get("bounds")

        height, width = values.shape
        for row in range(height):
            for col in range(width):
                code = int(values[row, col])
                cell_type = TensorGrid.decode_cell_type(code)
                value = self._convert_cell_type_to_value(cell_type)
                x = origin_x + col
                y = origin_y + row
                self.cells[(x, y)] = value
                self._update_bounds(x, y)

        if frontier_mask is not None:
            hint: Set[Tuple[int, int]] = set()
            height_f, width_f = frontier_mask.shape
            for row in range(height_f):
                for col in range(width_f):
                    if not frontier_mask[row, col]:
                        continue
                    hint.add((origin_x + col, origin_y + row))
            self._frontier_hint = hint if hint else None

        if bounds:
            self.bounds = tuple(bounds)
        else:
            self._recompute_bounds()
    
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

    def _convert_cell_type_to_value(self, cell_type: CellType) -> int:
        """Convertit CellType (enum) en valeur numérique"""
        return self._convert_type_to_value(cell_type.value)
    
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
        return self.bounds
    
    def is_in_bounds(self, x: int, y: int) -> bool:
        """Vérifie si une coordonnée est dans les bornes de la grille"""
        return (x, y) in self.cells

    def get_frontier_hint(self) -> Optional[Set[Tuple[int, int]]]:
        return self._frontier_hint.copy() if self._frontier_hint else None

    def _update_bounds(self, x: int, y: int) -> None:
        min_x, min_y, max_x, max_y = self.bounds
        self.bounds = (
            x if min_x == 0 and max_x == 0 else min(min_x, x),
            y if min_y == 0 and max_y == 0 else min(min_y, y),
            x if min_x == 0 and max_x == 0 else max(max_x, x),
            y if min_y == 0 and max_y == 0 else max(max_y, y),
        )

    def _recompute_bounds(self) -> None:
        if not self.cells:
            self.bounds = (0, 0, 0, 0)
            return
        xs = [coord[0] for coord in self.cells.keys()]
        ys = [coord[1] for coord in self.cells.keys()]
        self.bounds = (min(xs), min(ys), max(xs), max(ys))
