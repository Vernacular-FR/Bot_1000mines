"""Classification topologique des cellules JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Set, Tuple, Optional, TYPE_CHECKING

from PIL import Image

from src.lib.s3_storage.types import (
    Coord,
    GridCell,
    LogicalCellState,
    SolverStatus,
    StorageUpsert,
    ActiveRelevance,
    FrontierRelevance,
)
from src.config import CELL_SIZE, CELL_BORDER
from src.lib.s4_solver.types import SolverAction, ActionType

if TYPE_CHECKING:
    from src.lib.s0_browser.export_context import ExportContext


@dataclass(frozen=True)
class FrontierClassification:
    """Résultat de la classification topologique."""
    active: Set[Coord]
    frontier: Set[Coord]
    solved: Set[Coord]
    mine: Set[Coord]
    unrevealed: Set[Coord]


class FrontierClassifier:
    """
    Classifie les cellules en ACTIVE / FRONTIER / SOLVED / UNREVEALED
    à partir d'un snapshot de GridCell.
    """

    def __init__(self, cells: Dict[Coord, GridCell]):
        self._cells = cells

    def classify(self, target_coords: Optional[Iterable[Coord]] = None) -> FrontierClassification:
        """Classifie les cellules cibles et identifie la frontière globale."""
        active: Set[Coord] = set()
        solved: Set[Coord] = set()
        mine: Set[Coord] = set()
        
        target_coords_set = set(target_coords) if target_coords is not None else set(self._cells.keys())

        # 1. Identifier le statut des cellules cibles (ACTIVE, SOLVED, MINE)
        for coord in target_coords_set:
            cell = self._cells.get(coord)
            if not cell:
                continue
                
            if cell.logical_state == LogicalCellState.OPEN_NUMBER and cell.number_value is not None:
                if self._has_unrevealed_neighbor(coord):
                    active.add(coord)
                else:
                    solved.add(coord)
            elif cell.logical_state == LogicalCellState.EMPTY:
                solved.add(coord)
            elif cell.logical_state == LogicalCellState.CONFIRMED_MINE:
                mine.add(coord)

        # 2. Identifier la frontière globale
        # Une cellule est FRONTIER si elle est UNREVEALED et a au moins un voisin ACTIVE.
        # On doit considérer les cellules ACTIVE existantes ET celles qu'on vient de promouvoir.
        
        existing_active = {
            c for c, cell in self._cells.items() 
            if cell.solver_status == SolverStatus.ACTIVE
        }
        # État final des cellules actives après cette passe de classification
        all_active = (existing_active - target_coords_set) | active
        
        new_frontier: Set[Coord] = set()
        # Optimisation : on ne check que les voisins des cellules actives
        potential_frontier: Set[Coord] = set()
        for a_coord in all_active:
            for nb in self._neighbors(a_coord):
                potential_frontier.add(nb)
                
        for coord in potential_frontier:
            cell = self._cells.get(coord)
            # Une cellule est frontière si elle est UNREVEALED (et pas déjà classée comme MINE/SOLVED)
            if cell and cell.logical_state == LogicalCellState.UNREVEALED:
                new_frontier.add(coord)

        return FrontierClassification(
            active=active,
            frontier=new_frontier,
            solved=solved,
            mine=mine,
            unrevealed=set() # Plus utilisé
        )

    def _has_unrevealed_neighbor(self, coord: Coord) -> bool:
        for nb in self._neighbors(coord):
            neighbor = self._cells.get(nb)
            if neighbor and neighbor.logical_state == LogicalCellState.UNREVEALED:
                return True
        return False

    @staticmethod
    def _neighbors(coord: Coord):
        x, y = coord
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                yield x + dx, y + dy


class StatusAnalyzer:
    """
    Analyse topologique des cellules et promotion des status.
    Transforme JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED selon la topologie.
    Mappe aussi les actions solver (FLAG→SOLVED, SAFE/GUESS→TO_VISUALIZE).
    """

    @staticmethod
    def map_actions(
        cells: Dict[Coord, GridCell],
        actions: list,
    ) -> StorageUpsert:
        """Convertit les actions solver en changements topologiques.

        - FLAG → logical_state=CONFIRMED_MINE, topological_state=SOLVED
        - SAFE/GUESS → topological_state=TO_VISUALIZE

        Retourne un StorageUpsert avec les cellules mises à jour.
        """
        updated_cells: Dict[Coord, GridCell] = {}
        to_visualize: Set[Coord] = set()
        frontier_remove: Set[Coord] = set()

        for action in actions:
            coord = action.coord
            if coord not in cells:
                continue

            cell = cells[coord]

            if action.action == ActionType.FLAG:
                updated_cells[coord] = replace(
                    cell,
                    logical_state=LogicalCellState.CONFIRMED_MINE,
                    solver_status=SolverStatus.SOLVED,
                    topological_state=SolverStatus.SOLVED,
                    focus_level_active=None,
                    focus_level_frontier=None,
                )
                frontier_remove.add(coord)

            elif action.action in (ActionType.SAFE, ActionType.GUESS):
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.TO_VISUALIZE,
                    topological_state=SolverStatus.TO_VISUALIZE,
                    focus_level_active=None,
                    focus_level_frontier=None,
                )
                to_visualize.add(coord)
                frontier_remove.add(coord)

        return StorageUpsert(
            cells=updated_cells,
            to_visualize=to_visualize,
        )

    def analyze(
        self,
        cells: Dict[Coord, GridCell],
        *,
        target_status: SolverStatus = SolverStatus.JUST_VISUALIZED,
        overlay_ctx: Optional["ExportContext"] = None,
        base_image: Optional[Image.Image] = None,
        bounds: Optional[Tuple[int, int, int, int]] = None,
        stride: Optional[int] = None,
    ) -> StorageUpsert:
        """
        Analyse les cellules et retourne un StorageUpsert avec les status mis à jour.
        
        Reclasse uniquement les cellules ayant le status target_status.
        Préserve les statuts et focus_level des cellules déjà classées.
        """
        # Filtrer : reclasser uniquement les cellules cibles
        target_coords = [
            coord for coord, cell in cells.items()
            if cell.solver_status == target_status
        ]
        
        if not target_coords:
            return StorageUpsert(cells={}, to_visualize=set())

        # Classifier en utilisant TOUT le grid pour le contexte
        classifier = FrontierClassifier(cells)
        classification = classifier.classify(target_coords=target_coords)

        updated_cells: Dict[Coord, GridCell] = {}

        # Promouvoir les cellules ACTIVE
        for coord in classification.active:
            cell = cells[coord]
            # On ne met à jour que si le statut change (pour éviter de reset le focus REDUCED)
            if cell.solver_status != SolverStatus.ACTIVE:
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.ACTIVE,
                    focus_level_active=ActiveRelevance.TO_REDUCE,
                    focus_level_frontier=None
                )

        # Mettre à jour les cellules FRONTIER (promotions et démotions)
        # 1. Promotions
        for coord in classification.frontier:
            cell = cells[coord]
            if cell.solver_status != SolverStatus.FRONTIER:
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.FRONTIER,
                    focus_level_active=None,
                    focus_level_frontier=FrontierRelevance.TO_PROCESS
                )
        
        # 2. Démotions (si une cellule était FRONTIER mais ne l'est plus)
        # On ne le fait que si on a une vue globale (ce qui est le cas ici)
        for coord, cell in cells.items():
            if cell.solver_status == SolverStatus.FRONTIER and coord not in classification.frontier:
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.NONE,
                    focus_level_frontier=None
                )

        # Promouvoir les cellules SOLVED
        for coord in classification.solved:
            cell = cells[coord]
            if cell.solver_status != SolverStatus.SOLVED:
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.SOLVED,
                    focus_level_active=None,
                    focus_level_frontier=None
                )

        # Promouvoir les cellules MINE
        for coord in classification.mine:
            cell = cells[coord]
            if cell.solver_status != SolverStatus.MINE:
                updated_cells[coord] = replace(
                    cell,
                    solver_status=SolverStatus.MINE,
                    focus_level_active=None,
                    focus_level_frontier=None
                )

        upsert = StorageUpsert(
            cells=updated_cells,
            to_visualize=set(),
        )

        return upsert
