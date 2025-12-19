"""
FrontierClassifier – Wrapper de compatibilité vers StatusClassifier.

Ce fichier est conservé pour la compatibilité du code existant.
Toute la logique est déléguée à StatusClassifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set, Tuple

from src.lib.s3_storage.facade import GridCell, LogicalCellState
from .status_classifier import StatusClassifier

Coord = Tuple[int, int]


@dataclass(frozen=True)
class FrontierClassification:
    """Structure de retour pour compatibilité."""
    active: Set[Coord]
    frontier: Set[Coord]
    solved: Set[Coord]
    unrevealed: Set[Coord]


class FrontierClassifier:
    """
    Wrapper de compatibilité qui délègue à StatusClassifier.
    Conservé pour ne pas casser le code existant.
    """

    def __init__(self, cells: Dict[Coord, GridCell]):
        self._cells = cells

    def classify(self) -> FrontierClassification:
        """
        Classification directe comme l'original (pas de délégation à StatusClassifier).
        """
        active: Set[Coord] = set()
        solved: Set[Coord] = set()
        unrevealed: Set[Coord] = set()

        for coord, cell in self._cells.items():
            if cell.logical_state == LogicalCellState.OPEN_NUMBER and cell.number_value is not None:
                if self._has_unrevealed_neighbor(coord):
                    active.add(coord)
                else:
                    solved.add(coord)
            elif cell.logical_state in (LogicalCellState.EMPTY, LogicalCellState.CONFIRMED_MINE):
                solved.add(coord)
            elif cell.logical_state == LogicalCellState.UNREVEALED:
                unrevealed.add(coord)

        frontier: Set[Coord] = {
            coord for coord in unrevealed if self._has_active_neighbor(coord, active)
        }

        return FrontierClassification(
            active=active,
            frontier=frontier,
            solved=solved,
            unrevealed=unrevealed,
        )
    
    def _has_unrevealed_neighbor(self, coord: Coord) -> bool:
        """Vérifie si une cellule a des voisins non révélés."""
        for nb in self._neighbors(coord):
            neighbor = self._cells.get(nb)
            if neighbor and neighbor.logical_state == LogicalCellState.UNREVEALED:
                return True
        return False
    
    def _has_active_neighbor(self, coord: Coord, active: Set[Coord]) -> bool:
        """Vérifie si une cellule non révélée est voisine d'une ACTIVE."""
        for nb in self._neighbors(coord):
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
