from __future__ import annotations

from dataclasses import replace
from typing import Dict, Iterable, List, Set, Tuple

from src.lib.s3_storage.facade import (
    ActionStatus,
    Bounds,
    Coord,
    GridCell,
    LogicalCellState,
    SolverStatus,
)
from src.lib.s4_solver.s40_grid_analyzer.grid_extractor import SolverFrontierView
from src.lib.s4_solver.s41_propagator_solver.s410_propagator_pipeline import (
    PropagatorPipeline,
    PropagatorPipelineResult,
)
from src.lib.s4_solver.s43_csp_solver.csp_manager import CspManager
from src.lib.s4_solver.s42_csp_solver.segmentation import Segmentation


class HybridSolver:
    """
    Orchestrateur complet :
    1. PropagatorPipeline (phases locales 1→3)
    2. Segmentation + CSP exact en fallback seulement
    3. Probabilités par zone + actions
    """

    def __init__(self, view: SolverFrontierView, cells: Dict[Coord, GridCell]):
        self.view = view
        self.cells = cells
        self.segmentation: Segmentation | None = None
        self.zone_probabilities: Dict[int, float] = {}
        self.solutions_by_component: Dict[int, List] = {}
        self.pipeline_result: PropagatorPipelineResult | None = None
        self.safe_cells: Set[Tuple[int, int]] = set()
        self.flag_cells: Set[Tuple[int, int]] = set()
        self.csp_used: bool = False
        self.csp_manager: CspManager | None = None

    def solve(self) -> None:
        self.zone_probabilities.clear()
        self.solutions_by_component.clear()
        self.safe_cells.clear()
        self.flag_cells.clear()
        self.pipeline_result = None
        self.segmentation = None
        self.csp_manager = None
        self.csp_used = False

        # Étape 0: Propagation locale (phases 1→3)
        pipeline = PropagatorPipeline(self.cells)
        self.pipeline_result = pipeline.run()
        self.safe_cells.update(self.pipeline_result.safe_cells)
        self.flag_cells.update(self.pipeline_result.flag_cells)

        if self.pipeline_result.has_actions:
            return

        # Étape 1: Segmentation + CSP (fallback orchestré par CspManager)
        self.csp_used = True
        self.csp_manager = CspManager(self.view, self.cells)
        self.csp_manager.run(self.pipeline_result)
        self.segmentation = self.csp_manager.segmentation
        self.solutions_by_component = self.csp_manager.solutions_by_component
        self.zone_probabilities = self.csp_manager.zone_probabilities
        self.safe_cells.update(self.csp_manager.safe_cells)
        self.flag_cells.update(self.csp_manager.flag_cells)

    def get_safe_cells(self) -> List[Tuple[int, int]]:
        """Retourne les cellules sûres trouvées par réduction + motifs + CSP."""
        safe = set(self.safe_cells)
        if self.segmentation:
            for zone in self.segmentation.zones:
                prob = self.zone_probabilities.get(zone.id)
                if prob is not None and prob < 1e-6:
                    safe.update(zone.cells)
        return sorted(safe)

    def get_flag_cells(self) -> List[Tuple[int, int]]:
        """Retourne les cellules à marquer trouvées par réduction + motifs + CSP."""
        flags = set(self.flag_cells)
        if self.segmentation:
            for zone in self.segmentation.zones:
                prob = self.zone_probabilities.get(zone.id)
                if prob is not None and prob > 1 - 1e-6:
                    flags.update(zone.cells)
        return sorted(flags)

    def get_best_guess(self) -> Tuple[int, int, float] | None:
        if not self.segmentation:
            return None
        best_prob = 1.1
        best_cell: Tuple[int, int] | None = None
        for zone in self.segmentation.zones:
            prob = self.zone_probabilities.get(zone.id)
            if prob is None:
                continue
            if 1e-6 < prob < best_prob and zone.cells:
                best_prob = prob
                best_cell = zone.cells[0]
        if best_cell:
            return best_cell[0], best_cell[1], best_prob
        return None


Coord = Tuple[int, int]


def compute_bounds(coords: Set[Coord]) -> Bounds:
    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    min_x, max_x = min(xs) - 2, max(xs) + 3
    min_y, max_y = min(ys) - 2, max(ys) + 3
    return (min_x, min_y, max_x, max_y)


def build_metadata_updates(
    cells: Dict[Coord, GridCell],
    frontier_coords: Set[Coord],
    safe_cells: Iterable[Coord],
    flag_cells: Iterable[Coord],
) -> Dict[Coord, GridCell]:
    safe_set = set(safe_cells)
    flag_set = set(flag_cells)
    updated: Dict[Coord, GridCell] = {}

    for coord, cell in cells.items():
        desired_status = _classify_solver_status(coord, cell, frontier_coords, cells)
        desired_action = cell.action_status

        if coord in safe_set:
            desired_status = SolverStatus.SOLVED
            desired_action = ActionStatus.SAFE
        elif coord in flag_set:
            desired_status = SolverStatus.SOLVED
            desired_action = ActionStatus.FLAG
        elif desired_action != ActionStatus.NONE:
            desired_action = ActionStatus.NONE

        if desired_status != cell.solver_status or desired_action != cell.action_status:
            updated[coord] = replace(
                cell,
                solver_status=desired_status,
                action_status=desired_action,
            )

    return updated


def _classify_solver_status(
    coord: Coord,
    cell: GridCell,
    frontier_coords: Set[Coord],
    cells: Dict[Coord, GridCell],
) -> SolverStatus:
    if coord in frontier_coords and cell.logical_state == LogicalCellState.UNREVEALED:
        return SolverStatus.FRONTIER

    if cell.logical_state == LogicalCellState.OPEN_NUMBER:
        if _has_unrevealed_neighbor(coord, cells):
            return SolverStatus.ACTIVE
        return SolverStatus.SOLVED

    if cell.logical_state in {LogicalCellState.EMPTY, LogicalCellState.CONFIRMED_MINE}:
        return SolverStatus.SOLVED

    if cell.logical_state == LogicalCellState.UNREVEALED:
        return SolverStatus.NONE

    return cell.solver_status


def _has_unrevealed_neighbor(coord: Coord, cells: Dict[Coord, GridCell]) -> bool:
    for nx, ny in _iter_neighbors(coord):
        neighbor = cells.get((nx, ny))
        if neighbor and neighbor.logical_state == LogicalCellState.UNREVEALED:
            return True
    return False


def _iter_neighbors(coord: Coord):
    x, y = coord
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield x + dx, y + dy
