"""Contrôleur de storage - façade principale."""

from __future__ import annotations

from typing import Dict, Set, Optional, TYPE_CHECKING

from src.lib.s0_coordinates.types import GridBounds
from .types import (
    Bounds, Coord, GridCell, StorageUpsert,
    RawCellState, LogicalCellState, SolverStatus,
    ActiveRelevance, FrontierRelevance,
)
from .grid import GridStore

if TYPE_CHECKING:
    from src.lib.s2_vision.types import VisionResult


def _symbol_to_raw_state(symbol: str) -> RawCellState:
    """Convertit un symbole vision en RawCellState."""
    mapping = {
        "unrevealed": RawCellState.UNREVEALED,
        "empty": RawCellState.EMPTY,
        "number_1": RawCellState.NUMBER_1,
        "number_2": RawCellState.NUMBER_2,
        "number_3": RawCellState.NUMBER_3,
        "number_4": RawCellState.NUMBER_4,
        "number_5": RawCellState.NUMBER_5,
        "number_6": RawCellState.NUMBER_6,
        "number_7": RawCellState.NUMBER_7,
        "number_8": RawCellState.NUMBER_8,
        "flag": RawCellState.FLAG,
        "question_mark": RawCellState.QUESTION,
        "decor": RawCellState.DECOR,
        "exploded": RawCellState.EXPLODED,
    }
    return mapping.get(symbol, RawCellState.UNREVEALED)


def _symbol_to_logical_state(symbol: str) -> LogicalCellState:
    """Convertit un symbole vision en LogicalCellState."""
    if symbol.startswith("number_"):
        return LogicalCellState.OPEN_NUMBER
    if symbol == "empty":
        return LogicalCellState.EMPTY
    if symbol == "flag":
        return LogicalCellState.CONFIRMED_MINE
    if symbol == "exploded":
        # Cellule explosée = mine confirmée
        return LogicalCellState.CONFIRMED_MINE
    if symbol == "decor":
        # Décor = cellule résolue (vide)
        return LogicalCellState.EMPTY
    return LogicalCellState.UNREVEALED


def _symbol_to_number(symbol: str) -> Optional[int]:
    """Extrait le numéro d'un symbole."""
    if symbol.startswith("number_"):
        return int(symbol.split("_")[1])
    return None


class StorageController:
    """Façade principale pour le storage."""

    def __init__(self) -> None:
        self._store = GridStore()

    def apply_upsert(self, data: StorageUpsert) -> None:
        """Applique un batch de mises à jour."""
        self._store.apply_upsert(data)

    def get_snapshot(self, bounds: Optional[GridBounds] = None) -> Dict[Coord, GridCell]:
        """Retourne un snapshot des cellules."""
        if bounds is None:
            return self._store.get_all_cells()
        return self._store.get_cells_in_bounds(
            (bounds.min_col, bounds.min_row, bounds.max_col, bounds.max_row)
        )

    def get_frontier(self) -> Set[Coord]:
        """Retourne les coordonnées de la frontière."""
        return self._store.get_frontier()

    def get_active_set(self) -> Set[Coord]:
        """Retourne les coordonnées actives."""
        return self._store.get_active()

    def get_revealed(self) -> Set[Coord]:
        """Retourne les coordonnées révélées."""
        return self._store.get_revealed()

    def get_known(self) -> Set[Coord]:
        """Retourne les coordonnées connues."""
        return self._store.get_known()

    def get_to_visualize(self) -> Set[Coord]:
        """Retourne les coordonnées à re-capturer."""
        return self._store.get_to_visualize()
    
    def reset(self) -> None:
        """Réinitialise complètement le storage (vide toutes les cellules)."""
        self._store = GridStore()

    def update_from_vision(self, vision_result: "VisionResult") -> Dict[str, int]:
        """Met à jour le storage depuis les résultats vision (boîte noire).
        
        Ne marque JUST_VISUALIZED que les cellules nouvelles ou modifiées.
        Retourne les comptages de symboles pour debug.
        """
        cells: Dict[Coord, GridCell] = {}
        symbol_counts: Dict[str, int] = {}
        existing_snapshot = self.get_snapshot()

        for match in vision_result.matches:
            coord = (match.coord.col, match.coord.row)
            symbol = match.symbol
            
            # Déterminer le solver_status et focus levels
            existing_cell = existing_snapshot.get(coord)
            focus_active = ActiveRelevance.TO_REDUCE
            focus_frontier = FrontierRelevance.TO_PROCESS

            if existing_cell:
                # Cellule existe déjà : vérifier si elle a changé
                new_logical = _symbol_to_logical_state(symbol)
                new_number = _symbol_to_number(symbol)
                if (existing_cell.logical_state == new_logical and 
                    existing_cell.number_value == new_number):
                    # Pas de changement : préserver le solver_status et focus
                    solver_status = existing_cell.solver_status
                    focus_active = existing_cell.focus_level_active
                    focus_frontier = existing_cell.focus_level_frontier
                else:
                    # Changement détecté : marquer JUST_VISUALIZED
                    solver_status = SolverStatus.JUST_VISUALIZED
            else:
                # Nouvelle cellule : marquer JUST_VISUALIZED
                solver_status = SolverStatus.JUST_VISUALIZED
            
            cells[coord] = GridCell(
                coord=coord,
                raw_state=_symbol_to_raw_state(symbol),
                logical_state=_symbol_to_logical_state(symbol),
                number_value=_symbol_to_number(symbol),
                solver_status=solver_status,
                focus_level_active=focus_active,
                focus_level_frontier=focus_frontier,
            )
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

        self.apply_upsert(StorageUpsert(cells=cells))
        return symbol_counts
