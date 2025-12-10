#!/usr/bin/env python3
"""
CellAnalyzer - Analyse des cellules pour le solver
"""

from typing import Dict, Any, List, Optional
from src.lib.s3_tensor.cell import Cell, CellSymbol


class CellAnalyzer:
    """Analyseur de cellules pour le solver Minesweeper"""
    
    def __init__(self):
        pass
    
    def analyze_cell(self, cell: Cell) -> Dict[str, Any]:
        """
        Analyse une cellule et retourne ses caractéristiques
        
        Args:
            cell: Cellule à analyser
            
        Returns:
            Dictionnaire avec les caractéristiques de la cellule
        """
        return {
            'x': cell.x,
            'y': cell.y,
            'symbol': cell.symbol.value,
            'confidence': cell.confidence,
            'processing_status': cell.processing_status.value,
            'is_number': cell.is_number,
            'is_unknown': cell.is_unknown,
            'is_mine': cell.is_mine,
            'is_flagged': cell.is_flagged,
            'is_empty': cell.is_empty
        }
    
    def get_adjacent_cells(self, cell: Cell, grid_state: 'GridState') -> List[Cell]:
        """
        Récupère les cellules adjacentes à une cellule donnée
        
        Args:
            cell: Cellule de référence
            grid_state: État de la grille
            
        Returns:
            Liste des cellules adjacentes
        """
        adjacent = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = cell.x + dx, cell.y + dy
                adj_cell = grid_state.get_cell(nx, ny)
                if adj_cell:
                    adjacent.append(adj_cell)
        return adjacent
    
    def count_adjacent_mines(self, cell: Cell, grid_state: 'GridState') -> int:
        """
        Compte les mines adjacentes à une cellule
        
        Args:
            cell: Cellule de référence
            grid_state: État de la grille
            
        Returns:
            Nombre de mines adjacentes
        """
        count = 0
        for adj_cell in self.get_adjacent_cells(cell, grid_state):
            if adj_cell.is_mine or adj_cell.is_flagged:
                count += 1
        return count
    
    def count_adjacent_unknown(self, cell: Cell, grid_state: 'GridState') -> int:
        """
        Compte les cellules inconnues adjacentes à une cellule
        
        Args:
            cell: Cellule de référence
            grid_state: État de la grille
            
        Returns:
            Nombre de cellules inconnues adjacentes
        """
        count = 0
        for adj_cell in self.get_adjacent_cells(cell, grid_state):
            if adj_cell.is_unknown:
                count += 1
        return count
