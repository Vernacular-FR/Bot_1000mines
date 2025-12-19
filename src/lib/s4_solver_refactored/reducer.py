"""Réduction par contraintes simples (déduction logique)."""

from typing import Dict, Set, Tuple, List

from src.lib.s0_coordinates.types import Coord
from .types import GridCell, SolverAction, ActionType


class FrontierReducer:
    """Réduction de la frontière par déductions logiques simples."""

    def __init__(self, cells: Dict[Tuple[int, int], GridCell]):
        self.cells = cells
        self.safe_cells: Set[Tuple[int, int]] = set()
        self.flag_cells: Set[Tuple[int, int]] = set()

    def reduce(self, frontier: Set[Tuple[int, int]], active_set: Set[Tuple[int, int]]) -> bool:
        """
        Applique les règles de réduction.
        Retourne True si des déductions ont été faites.
        """
        changed = True
        total_changes = False

        while changed:
            changed = False
            for coord in list(active_set):
                cell = self.cells.get(coord)
                if not cell or not cell.is_number:
                    continue

                neighbors = self._get_unrevealed_neighbors(coord, frontier)
                flagged = self._count_flagged_neighbors(coord)
                
                remaining_mines = cell.adjacent_mine_count - flagged
                
                # Règle 1: Toutes les mines trouvées → voisins safe
                if remaining_mines == 0 and neighbors:
                    for n in neighbors:
                        if n not in self.safe_cells and n not in self.flag_cells:
                            self.safe_cells.add(n)
                            changed = True
                            total_changes = True

                # Règle 2: Autant de voisins que de mines restantes → tous flags
                if remaining_mines == len(neighbors) and remaining_mines > 0:
                    for n in neighbors:
                        if n not in self.flag_cells and n not in self.safe_cells:
                            self.flag_cells.add(n)
                            changed = True
                            total_changes = True

        return total_changes

    def get_actions(self) -> List[SolverAction]:
        """Retourne les actions déduites."""
        actions = []
        
        for coord_tuple in self.safe_cells:
            actions.append(SolverAction(
                coord=Coord(row=coord_tuple[0], col=coord_tuple[1]),
                action=ActionType.CLICK,
                confidence=1.0,
            ))
        
        for coord_tuple in self.flag_cells:
            actions.append(SolverAction(
                coord=Coord(row=coord_tuple[0], col=coord_tuple[1]),
                action=ActionType.FLAG,
                confidence=1.0,
            ))
        
        return actions

    def _get_unrevealed_neighbors(self, coord: Tuple[int, int], frontier: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Retourne les voisins non révélés d'une cellule."""
        row, col = coord
        neighbors = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                n = (row + dr, col + dc)
                if n in frontier and n not in self.safe_cells:
                    neighbors.append(n)
        return neighbors

    def _count_flagged_neighbors(self, coord: Tuple[int, int]) -> int:
        """Compte les voisins flaggés d'une cellule."""
        row, col = coord
        count = 0
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                n = (row + dr, col + dc)
                cell = self.cells.get(n)
                if cell and cell.is_flagged:
                    count += 1
                if n in self.flag_cells:
                    count += 1
        return count
