"""Pipeline 2 : Mapper les actions solver et gérer les retrogressions.

Après que le solver émet des actions (SAFE/FLAG/GUESS), ce module :
- FLAG → logical_state=CONFIRMED_MINE, solver_status=MINE
- SAFE/GUESS → solver_status=TO_VISUALIZE
- SOLVED_CELLS → solver_status=SOLVED
- Rétrograde les ACTIVE/FRONTIER non résolues en PROCESSED/REDUCED
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Set

from src.lib.s3_storage.types import (
    Coord,
    GridCell,
    LogicalCellState,
    SolverStatus,
    StorageUpsert,
    ActiveRelevance,
    FrontierRelevance,
)
from src.lib.s4_solver.types import SolverAction, ActionType


class ActionMapper:
    """Mapper les actions solver et gérer les retrogressions."""

    @staticmethod
    def map_actions(
        cells: Dict[Coord, GridCell],
        actions: List[SolverAction],
        solved_cells: Set[Coord] = None,
    ) -> StorageUpsert:
        """Convertit les actions solver en changements topologiques.

        - FLAG → logical_state=CONFIRMED_MINE, solver_status=MINE
        - SAFE/GUESS → solver_status=TO_VISUALIZE
        - SOLVED_CELLS → solver_status=SOLVED
        - Rétrograde les ACTIVE/FRONTIER non résolues

        Retourne un StorageUpsert avec les cellules mises à jour.
        """
        updated_cells: Dict[Coord, GridCell] = {}
        to_visualize: Set[Coord] = set()
        frontier_remove: Set[Coord] = set()
        active_remove: Set[Coord] = set()
        
        # Collecter les coordonnées des actions résolues
        resolved_coords: Set[Coord] = set()
        solved_cells = solved_cells or set()

        # 1. Traiter les actions explicites (SAFE/FLAG/GUESS)
        for action in actions:
            coord = action.coord
            if coord not in cells:
                continue

            cell = cells[coord]
            resolved_coords.add(coord)

            if action.action == ActionType.FLAG:
                updated_cells[coord] = replace(
                    cell,
                    logical_state=LogicalCellState.CONFIRMED_MINE,
                    solver_status=SolverStatus.MINE,
                    focus_level_active=ActiveRelevance.TO_REDUCE,
                    focus_level_frontier=FrontierRelevance.TO_PROCESS,
                )
                frontier_remove.add(coord)

            elif action.action in (ActionType.SAFE, ActionType.GUESS):
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.TO_VISUALIZE,
                    focus_level_active=ActiveRelevance.TO_REDUCE,
                    focus_level_frontier=FrontierRelevance.TO_PROCESS,
                )
                to_visualize.add(coord)
                frontier_remove.add(coord)

        # 2. Traiter les cellules ACTIVE résolues (transition vers SOLVED)
        for coord in solved_cells:
            if coord in resolved_coords or coord not in cells:
                continue
            
            cell = cells[coord]
            if cell.solver_status == SolverStatus.ACTIVE:
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.SOLVED,
                    focus_level_active=ActiveRelevance.REDUCED,
                )
                resolved_coords.add(coord)
                active_remove.add(coord)

        # 3. Rétrograder les ACTIVE/FRONTIER non résolues (Focus level uniquement)
        for coord, cell in cells.items():
            if coord in resolved_coords:
                continue
            
            if cell.solver_status == SolverStatus.ACTIVE:
                updated_cells[coord] = replace(
                    cell,
                    focus_level_active=ActiveRelevance.REDUCED,
                )
                active_remove.add(coord)
            
            elif cell.solver_status == SolverStatus.FRONTIER:
                updated_cells[coord] = replace(
                    cell,
                    focus_level_frontier=FrontierRelevance.PROCESSED,
                )
                frontier_remove.add(coord)

        return StorageUpsert(
            cells=updated_cells,
            to_visualize=to_visualize,
        )
