from __future__ import annotations

from typing import Dict, List, Set, Tuple
from dataclasses import dataclass

from src.lib.s3_storage.facade import GridCell, LogicalCellState


@dataclass
class PatternResult:
    """Résultat d'une détection de motif."""
    safe_cells: Set[Tuple[int, int]]
    flag_cells: Set[Tuple[int, int]]
    reasoning: str


class PatternEngine:
    """
    Moteur de résolution par motifs pour les configurations simples.
    Gère les cas où le CSP ne peut pas résoudre (zones partiellement hors champ).
    """

    def __init__(self, cells: Dict[Tuple[int, int], GridCell]):
        self.cells = cells
        self.numbered_cells = [
            coord for coord, cell in cells.items() 
            if cell.logical_state == LogicalCellState.OPEN_NUMBER and cell.number_value is not None
        ]

    def solve_patterns(self) -> PatternResult:
        """
        Applique tous les motifs connus pour identifier les cellules sûres/mines.
        """
        safe_cells: Set[Tuple[int, int]] = set()
        flag_cells: Set[Tuple[int, int]] = set()
        reasoning_parts: List[str] = []

        # Motif 1-1 : deux cellules inconnues autour d'un 1
        for coord in self.numbered_cells:
            pattern_result = self._check_1_1_pattern(coord)
            safe_cells.update(pattern_result.safe_cells)
            flag_cells.update(pattern_result.flag_cells)
            if pattern_result.reasoning:
                reasoning_parts.append(pattern_result.reasoning)

        # Motif 1-2-1 : configuration en triangle
        for coord in self.numbered_cells:
            pattern_result = self._check_1_2_1_pattern(coord)
            safe_cells.update(pattern_result.safe_cells)
            flag_cells.update(pattern_result.flag_cells)
            if pattern_result.reasoning:
                reasoning_parts.append(pattern_result.reasoning)

        # Motif 1-2 : deux cellules inconnues autour d'un 2
        for coord in self.numbered_cells:
            pattern_result = self._check_1_2_pattern(coord)
            safe_cells.update(pattern_result.safe_cells)
            flag_cells.update(pattern_result.flag_cells)
            if pattern_result.reasoning:
                reasoning_parts.append(pattern_result.reasoning)

        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "No patterns found"
        return PatternResult(safe_cells=safe_cells, flag_cells=flag_cells, reasoning=reasoning)

    def _get_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Retourne les 8 voisins d'une cellule."""
        neighbors = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (nx, ny) in self.cells:
                    neighbors.append((nx, ny))
        return neighbors

    def _check_1_1_pattern(self, coord: Tuple[int, int]) -> PatternResult:
        """
        Motif 1-1 : un chiffre 1 avec exactement 2 voisins inconnus.
        Si l'un des voisins est déjà un drapeau, l'autre est sûr.
        """
        x, y = coord
        cell = self.cells[coord]
        if cell.number_value != 1:
            return PatternResult(set(), set(), "")

        neighbors = self._get_neighbors(x, y)
        unknown_neighbors = [
            (nx, ny) for nx, ny in neighbors 
            if self.cells[(nx, ny)].logical_state == LogicalCellState.UNREVEALED
        ]
        flag_neighbors = [
            (nx, ny) for nx, ny in neighbors 
            if self.cells[(nx, ny)].logical_state == LogicalCellState.CONFIRMED_MINE
        ]

        if len(unknown_neighbors) == 2 and len(flag_neighbors) == 1:
            # L'unique cellule inconnue restante est sûre
            safe_cells = set(unknown_neighbors)
            return PatternResult(safe_cells, set(), f"1-1 pattern at {coord}")

        return PatternResult(set(), set(), "")

    def _check_1_2_1_pattern(self, coord: Tuple[int, int]) -> PatternResult:
        """
        Motif 1-2-1 : configuration en triangle.
        Si un 1 est adjacent à un 2 qui a exactement 2 inconnus,
        et le 1 partage un de ces inconnus, alors l'autre inconnu du 2 est sûr.
        """
        x, y = coord
        cell = self.cells[coord]
        if cell.number_value != 1:
            return PatternResult(set(), set(), "")

        # Chercher un 2 adjacent
        neighbors = self._get_neighbors(x, y)
        for nx, ny in neighbors:
            neighbor_cell = self.cells[(nx, ny)]
            if neighbor_cell.logical_state == LogicalCellState.OPEN_NUMBER and neighbor_cell.number_value == 2:
                # Vérifier la configuration 1-2-1
                two_neighbors = self._get_neighbors(nx, ny)
                two_unknowns = [
                    (tx, ty) for tx, ty in two_neighbors 
                    if self.cells[(tx, ty)].logical_state == LogicalCellState.UNREVEALED
                ]
                
                if len(two_unknowns) == 2:
                    # Le 1 partage-t-il un inconnu avec le 2?
                    one_unknowns = [
                        (ox, oy) for ox, oy in neighbors 
                        if self.cells[(ox, oy)].logical_state == LogicalCellState.UNREVEALED
                    ]
                    shared = set(one_unknowns) & set(two_unknowns)
                    
                    if len(shared) == 1:
                        # L'autre inconnu du 2 est sûr
                        safe_cell = (set(two_unknowns) - shared).pop()
                        return PatternResult({safe_cell}, set(), f"1-2-1 pattern at {coord}")

        return PatternResult(set(), set(), "")

    def _check_1_2_pattern(self, coord: Tuple[int, int]) -> PatternResult:
        """
        Motif 1-2 : un 1 adjacent à un 2 avec exactement 2 inconnus.
        Si le 1 partage un inconnu avec le 2, l'autre inconnu du 2 est une mine.
        """
        x, y = coord
        cell = self.cells[coord]
        if cell.number_value != 1:
            return PatternResult(set(), set(), "")

        # Chercher un 2 adjacent
        neighbors = self._get_neighbors(x, y)
        for nx, ny in neighbors:
            neighbor_cell = self.cells[(nx, ny)]
            if neighbor_cell.logical_state == LogicalCellState.OPEN_NUMBER and neighbor_cell.number_value == 2:
                # Vérifier la configuration
                two_neighbors = self._get_neighbors(nx, ny)
                two_unknowns = [
                    (tx, ty) for tx, ty in two_neighbors 
                    if self.cells[(tx, ty)].logical_state == LogicalCellState.UNREVEALED
                ]
                
                if len(two_unknowns) == 2:
                    # Le 1 partage-t-il un inconnu avec le 2?
                    one_unknowns = [
                        (ox, oy) for ox, oy in neighbors 
                        if self.cells[(ox, oy)].logical_state == LogicalCellState.UNREVEALED
                    ]
                    shared = set(one_unknowns) & set(two_unknowns)
                    
                    if len(shared) == 1:
                        # L'autre inconnu du 2 est une mine
                        flag_cell = (set(two_unknowns) - shared).pop()
                        return PatternResult(set(), {flag_cell}, f"1-2 pattern at {coord}")

        return PatternResult(set(), set(), "")
