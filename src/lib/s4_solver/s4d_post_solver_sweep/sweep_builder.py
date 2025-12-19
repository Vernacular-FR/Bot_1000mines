"""Générateur d'actions de sweep post-solver."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from src.lib.s3_storage.types import Coord, GridCell, SolverStatus, LogicalCellState
from src.lib.s4_solver.types import SolverAction, ActionType

def _iter_neighbors(coord: Coord) -> Tuple[Coord, ...]:
    """Itère sur les 8 voisins d'une coordonnée."""
    col, row = coord
    neighbors = []
    for dc in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if dc == 0 and dr == 0:
                continue
            neighbors.append((col + dc, row + dr))
    return tuple(neighbors)


def build_sweep_actions(cells: Dict[Coord, GridCell]) -> List[SolverAction]:
    """Génère des actions de sweep bonus après la phase solver.
    
    Cible uniquement les voisins ACTIVE des cellules TO_VISUALIZE pour rafraîchir
    les zones et faciliter la propagation des informations.
    
    Args:
        cells: Snapshot des cellules du storage
    
    Returns:
        Liste d'actions SAFE pour les cellules à rafraîchir
    """
    # Identifier les cellules à visualiser
    to_visualize: Set[Coord] = {
        coord for coord, cell in cells.items()
        if cell.solver_status == SolverStatus.TO_VISUALIZE
    }

    # Cibler uniquement les voisins ACTIVE des TO_VISUALIZE (pas les TO_VISUALIZE elles-mêmes)
    # Exclure les SOLVED qui auraient pu être créés par le pipeline 2
    targets: Set[Coord] = set()
    for coord in to_visualize:
        for nb in _iter_neighbors(coord):
            nb_cell = cells.get(nb)
            if nb_cell and nb_cell.solver_status == SolverStatus.ACTIVE:
                # Vérifier que la cellule n'est pas devenue SOLVED après pipeline 2
                if nb_cell.logical_state != LogicalCellState.OPEN_NUMBER or nb_cell.number_value is None:
                    continue
                # Vérifier si effective_value != 0 (sinon c'est SOLVED)
                neighbor_mines = sum(
                    1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    if (dx != 0 or dy != 0)
                    and cells.get((nb[0] + dx, nb[1] + dy))
                    and cells[(nb[0] + dx, nb[1] + dy)].logical_state == LogicalCellState.CONFIRMED_MINE
                )
                effective_value = nb_cell.number_value - neighbor_mines
                if effective_value > 0:
                    targets.add(nb)

    # Générer les actions SAFE
    actions: List[SolverAction] = []
    for coord in sorted(targets):
        actions.append(
            SolverAction(
                coord=coord,
                action=ActionType.SAFE,
                confidence=1.0,
                reasoning="sweep",
            )
        )
    return actions
