from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

from src.lib.s3_storage.facade import GridCell, SolverStatus
from src.lib.s4_solver.facade import SolverAction, SolverActionType

Coord = Tuple[int, int]


def _iter_neighbors(coord: Coord):
    x, y = coord
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield x + dx, y + dy


def build_cleanup_actions(cells: Dict[Coord, GridCell]) -> List[SolverAction]:
    """
    Génère des cleanups bonus après la phase solver (safe/flag/guess).
    - Cible les cases ACTIVE marquées TO_REDUCE
    - Étend aux ACTIVE voisines (facilite le rafraîchissement local)
    """
    to_visualize: Set[Coord] = {
        coord for coord, cell in cells.items() if cell.solver_status == SolverStatus.TO_VISUALIZE
    }

    targets: Set[Coord] = set(to_visualize)
    for coord in list(to_visualize):
        for nb in _iter_neighbors(coord):
            nb_cell = cells.get(nb)
            if not nb_cell:
                continue
            if nb_cell.solver_status == SolverStatus.ACTIVE:
                targets.add(nb)

    actions: List[SolverAction] = []
    for coord in sorted(targets):
        actions.append(
            SolverAction(
                cell=coord,
                type=SolverActionType.CLICK,
                confidence=1.0,
                reasoning="cleanup to_visualize",
            )
        )
    return actions
