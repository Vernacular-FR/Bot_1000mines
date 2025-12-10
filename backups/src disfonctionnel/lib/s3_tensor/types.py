#!/usr/bin/env python3
"""
Types et structures de données pour la reconnaissance des cases du démineur
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import numpy as np
from PIL import Image

class CellType(Enum):
    """Types de cases possibles dans le démineur"""
    EMPTY = "empty"           # Case vide (que du gris)
    UNREVEALED = "unrevealed" # Case non activée (que du blanc)
    FLAG = "flag"             # Drapeau (blanc + noir + rouge)
    MINE = "mine"             # Mine (gris + rouge/noir)
    NUMBER_1 = "number_1"     # Chiffre 1 (gris + bleu)
    NUMBER_2 = "number_2"     # Chiffre 2 (gris + vert)
    NUMBER_3 = "number_3"     # Chiffre 3 (gris + rouge)
    NUMBER_4 = "number_4"     # Chiffre 4 (gris + violet)
    NUMBER_5 = "number_5"     # Chiffre 5 (gris + orange)
    NUMBER_6 = "number_6"     # Chiffre 6 (gris + cyan)
    NUMBER_7 = "number_7"     # Chiffre 7 (gris + noir)
    NUMBER_8 = "number_8"     # Chiffre 8 (gris + gris foncé)
    UNKNOWN = "unknown"       # Type non reconnu

@dataclass
class ColorInfo:
    """Information sur une couleur détectée"""
    rgb: Tuple[int, int, int]
    hex: str
    proportion: float
    category: str  # 'white', 'black', 'red', 'blue', 'green', etc.

@dataclass
class CellAnalysis:
    """Résultat de l'analyse d'une case"""
    coordinates: Tuple[int, int]  # (x, y) dans la grille
    cell_type: CellType
    confidence: float  # 0.0 à 1.0
    colors: List[ColorInfo]
    raw_image: Optional[Image.Image] = None  # Pour debugging
    analysis_timestamp: datetime = None
    
    def __post_init__(self):
        if self.analysis_timestamp is None:
            self.analysis_timestamp = datetime.now()

@dataclass
class GridAnalysis:
    """Résultat de l'analyse complète d'une grille"""
    grid_bounds: Tuple[int, int, int, int]  # (start_x, start_y, end_x, end_y)
    cells: Dict[Tuple[int, int], CellAnalysis]  # (x, y) → CellAnalysis
    analysis_timestamp: datetime = None
    
    def __post_init__(self):
        if self.analysis_timestamp is None:
            self.analysis_timestamp = datetime.now()
    
    def get_cell_count(self) -> int:
        """Retourne le nombre de cellules analysées"""
        return len(self.cells)
    
    def get_cells_by_type(self, cell_type: CellType) -> List[CellAnalysis]:
        """Retourne toutes les cellules d'un type spécifique"""
        return [cell for cell in self.cells.values() if cell.cell_type == cell_type]
    
    def get_mine_positions(self) -> List[Tuple[int, int]]:
        """Retourne les positions des mines"""
        return [coords for coords, cell in self.cells.items() if cell.cell_type == CellType.MINE]
    
    def get_unrevealed_positions(self) -> List[Tuple[int, int]]:
        """Retourne les positions des cases non révélées"""
        return [coords for coords, cell in self.cells.items() if cell.cell_type == CellType.UNREVEALED]
    
    def get_flag_positions(self) -> List[Tuple[int, int]]:
        """Retourne les positions des drapeaux"""
        return [coords for coords, cell in self.cells.items() if cell.cell_type == CellType.FLAG]
    
    def get_number_positions(self) -> Dict[int, List[Tuple[int, int]]]:
        """Retourne les positions des chiffres groupés par valeur"""
        number_positions = {}
        for coords, cell in self.cells.items():
            if cell.cell_type.value.startswith('number_'):
                number = int(cell.cell_type.value.split('_')[1])
                if number not in number_positions:
                    number_positions[number] = []
                number_positions[number].append(coords)
        return number_positions
    
    def get_summary(self) -> Dict[str, Any]:
        """Retourne un résumé de l'analyse"""
        summary = {
            'total_cells': self.get_cell_count(),
            'grid_bounds': self.grid_bounds,
            'analysis_timestamp': self.analysis_timestamp.isoformat(),
            'cell_types': {}
        }
        
        # Compter les cellules par type
        for cell_type in CellType:
            cells_of_type = self.get_cells_by_type(cell_type)
            summary['cell_types'][cell_type.value] = {
                'count': len(cells_of_type),
                'positions': [cell.coordinates for cell in cells_of_type]
            }
        
        return summary
