"""Module de promotion/déclassement des focus levels.

Réveille les voisins des cellules nouvellement ACTIVE/SOLVED/TO_VISUALIZE :
- voisins ACTIVE → focus_level_active = TO_REDUCE
- voisins FRONTIER → focus_level_frontier = TO_PROCESS

Centralise 100% de la logique de gestion des focus levels.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, Set, Iterable

from src.lib.s3_storage.types import (
    Coord,
    GridCell,
    SolverStatus,
    StorageUpsert,
    ActiveRelevance,
    FrontierRelevance,
)


class FocusActualizer:
    """Module stateless pour la gestion des promotions de focus level."""

    @staticmethod
    def promote_focus(
        cells: Dict[Coord, GridCell],
        newly_changed: Set[Coord],
    ) -> StorageUpsert:
        """Réveille les voisins des cellules qui viennent de changer.

        newly_changed : coordonnées des cellules nouvellement ACTIVE/SOLVED/TO_VISUALIZE.

        Pour chaque voisin :
        - Si ACTIVE avec focus REDUCED → repasse TO_REDUCE
        - Si FRONTIER avec focus PROCESSED → repasse TO_PROCESS

        Retourne un StorageUpsert avec uniquement les focus levels mis à jour.
        """
        updated_cells: Dict[Coord, GridCell] = {}

        def _neighbors(coord: Coord) -> Iterable[Coord]:
            x, y = coord
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nb = (x + dx, y + dy)
                    if nb in cells:
                        yield nb

        for center in newly_changed:
            if center not in cells:
                continue
            for nb in _neighbors(center):
                cell = cells[nb]
                if cell.solver_status == SolverStatus.ACTIVE:
                    if cell.focus_level_active in (None, ActiveRelevance.REDUCED):
                        updated_cells[nb] = replace(
                            cell,
                            focus_level_active=ActiveRelevance.TO_REDUCE,
                        )
                elif cell.solver_status == SolverStatus.FRONTIER:
                    if cell.focus_level_frontier in (None, FrontierRelevance.PROCESSED):
                        updated_cells[nb] = replace(
                            cell,
                            focus_level_frontier=FrontierRelevance.TO_PROCESS,
                        )
                # NOUVEAU : Réveiller les SOLVED si un voisin change (ex: régression suite à échec action)
                elif cell.solver_status == SolverStatus.SOLVED:
                    updated_cells[nb] = replace(
                        cell,
                        solver_status=SolverStatus.ACTIVE,
                        focus_level_active=ActiveRelevance.TO_REDUCE,
                    )

        return StorageUpsert(
            cells=updated_cells,
            to_visualize=set(),
        )

    @staticmethod
    def demote_active_to_reduced(
        cells: Dict[Coord, GridCell],
        processed_coords: Set[Coord],
    ) -> StorageUpsert:
        """Marque les cellules ACTIVE traitées comme REDUCED.

        processed_coords : coordonnées des cellules ACTIVE qui ont été traitées
        par le reducer et n'ont plus rien à apporter dans l'état courant.
        """
        updated_cells: Dict[Coord, GridCell] = {}

        for coord in processed_coords:
            if coord not in cells:
                continue
            cell = cells[coord]
            if cell.solver_status == SolverStatus.ACTIVE:
                if cell.focus_level_active == ActiveRelevance.TO_REDUCE:
                    updated_cells[coord] = replace(
                        cell,
                        focus_level_active=ActiveRelevance.REDUCED,
                    )

        return StorageUpsert(
            cells=updated_cells,
            to_visualize=set(),
        )

    @staticmethod
    def demote_frontier_to_processed(
        cells: Dict[Coord, GridCell],
        processed_coords: Set[Coord],
    ) -> StorageUpsert:
        """Marque les cellules FRONTIER traitées comme PROCESSED.

        processed_coords : coordonnées des cellules FRONTIER qui ont été traitées
        par le CSP et n'ont plus rien à apporter dans l'état courant.
        """
        updated_cells: Dict[Coord, GridCell] = {}

        for coord in processed_coords:
            if coord not in cells:
                continue
            cell = cells[coord]
            if cell.solver_status == SolverStatus.FRONTIER:
                if cell.focus_level_frontier == FrontierRelevance.TO_PROCESS:
                    updated_cells[coord] = replace(
                        cell,
                        focus_level_frontier=FrontierRelevance.PROCESSED,
                    )

        return StorageUpsert(
            cells=updated_cells,
            to_visualize=set(),
        )
