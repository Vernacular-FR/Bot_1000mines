from __future__ import annotations

from typing import Dict, List, Set, Tuple

from src.lib.s3_storage.facade import Coord
from src.lib.s4_solver.s40_grid_analyzer.grid_extractor import SolverFrontierView
from src.lib.s4_solver.s41_propagator_solver.s410_propagator_pipeline import (
    PropagatorPipeline,
    PropagatorPipelineResult,
)
from src.lib.s4_solver.s43_csp_solver.s43_stability_evaluator import (
    StabilityConfig,
    StabilityEvaluator,
)
from src.lib.s4_solver.s42_csp_solver.csp_solver import CSPSolver
from src.lib.s4_solver.s42_csp_solver.segmentation import Segmentation


class CspManager:
    """Encapsule segmentation + stabilité + CSP + probabilités."""

    def __init__(self, view: SolverFrontierView, cells: Dict[Coord, object]):
        self.view = view
        self.cells = cells
        self.segmentation: Segmentation | None = None
        self.csp: CSPSolver | None = None
        self.stability = StabilityEvaluator(StabilityConfig())
        self.zone_probabilities: Dict[int, float] = {}
        self.solutions_by_component: Dict[int, List] = {}
        self.safe_cells: Set[Coord] = set()
        self.flag_cells: Set[Coord] = set()

    def run(self, pipeline_result: PropagatorPipelineResult) -> None:
        self.segmentation = Segmentation(self.view)
        self.csp = CSPSolver(self.view)

        eligible_components = self.stability.determine_eligible_components(
            self.segmentation,
            pipeline_result.progress_cells(),
        )

        for component in self.segmentation.components:
            if component.id not in eligible_components:
                continue

            solutions = self.csp.solve_component(component)
            if not solutions:
                continue

            self.solutions_by_component[component.id] = solutions
            total_weight = 0.0
            zone_weighted_mines: Dict[int, float] = {z.id: 0.0 for z in component.zones}

            for sol in solutions:
                weight = sol.get_prob_weight(self.segmentation.zones)
                total_weight += weight
                for zid, mines in sol.zone_assignment.items():
                    zone_weighted_mines[zid] += mines * weight

            if total_weight <= 0:
                continue

            for zone in component.zones:
                prob = (zone_weighted_mines[zone.id] / total_weight) / len(zone.cells)
                self.zone_probabilities[zone.id] = prob
                if prob < 1e-6:
                    self.safe_cells.update(zone.cells)
                elif prob > 1 - 1e-6:
                    self.flag_cells.update(zone.cells)
