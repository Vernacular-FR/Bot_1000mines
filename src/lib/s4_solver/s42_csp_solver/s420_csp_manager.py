from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

from src.lib.s3_storage.facade import (
    Coord,
    GridCell,
    LogicalCellState,
    SolverStatus,
)
from src.lib.s4_solver.s40_states_analyzer.grid_classifier import FrontierClassifier
from src.lib.s4_solver.s40_states_analyzer.grid_extractor import SolverFrontierView
from src.lib.s4_solver.s41_propagator_solver.s410_propagator_pipeline import (
    PropagatorPipeline,
    PropagatorPipelineResult,
)
from src.lib.s4_solver.s42_csp_solver.s421_frontiere_reducer import (
    IterativePropagator,
    PropagationResult,
)
from src.lib.s4_solver.s42_csp_solver.s422_segmentation import Segmentation
from src.lib.s4_solver.s42_csp_solver.s424_csp_solver import CSPSolver
from src.lib.s4_solver.s42_csp_solver.s423_range_filter import (
    ComponentRangeConfig,
    ComponentRangeFilter,
)
from src.lib.s4_solver.facade import SolverAction, SolverActionType
from src.lib.s4_solver.s49_overlays.s491_states_overlay import render_states_overlay
from src.lib.s4_solver.s49_overlays.s492_segmentation_overlay import render_segmentation_overlay
from src.lib.s4_solver.s49_overlays.s493_actions_overlay import render_actions_overlay
from src.lib.s4_solver.s49_overlays.s494_combined_overlay import render_combined_overlay


class CspManager:
    """Encapsule segmentation + stabilité + CSP + probabilités."""

    def __init__(
        self,
        view: SolverFrontierView,
        cells: Dict[Coord, GridCell],
        *,
        stability_config: ComponentRangeConfig | None = None,
        use_stability: bool = True,
        overlay_metadata: Optional[Dict] = None,
    ):
        self.view = view
        self.cells = cells
        self.segmentation: Segmentation | None = None
        self.csp: CSPSolver | None = None
        self.use_stability = use_stability
        self.stability_config = stability_config or ComponentRangeConfig()
        self.stability = (
            ComponentRangeFilter(self.stability_config) if self.use_stability else None
        )
        self.zone_probabilities: Dict[int, float] = {}
        self.solutions_by_component: Dict[int, List] = {}
        self.safe_cells: Set[Coord] = set()
        self.flag_cells: Set[Coord] = set()
        self.reducer_result: PropagationResult | None = None
        self.overlay_metadata = overlay_metadata or {}

    def run(self, pipeline_result: PropagatorPipelineResult) -> None:
        """Backward-compatible entrypoint → pipeline pur."""
        self.run_pure(pipeline_result)

    def run_pure(self, pipeline_result: PropagatorPipelineResult) -> None:
        """CSP uniquement (suppose que la propagation amont est déjà faite)."""
        self._reset_state()
        self._execute_csp(pipeline_result)

    def run_with_frontier_reducer(self) -> None:
        """
        Pipeline complet : applique un FrontiereReducer minimal,
        met à jour les cells/view puis exécute le CSP pur.
        """
        self._reset_state()
        reducer = IterativePropagator(self.cells)
        reducer_result = reducer.solve_with_zones()
        self.reducer_result = reducer_result
        self._apply_reducer_actions(reducer_result)
        pipeline_result = self._build_pipeline_stub(reducer_result)
        self._execute_csp(pipeline_result)

    def _reset_state(self) -> None:
        self.segmentation = None
        self.csp = None
        self.zone_probabilities.clear()
        self.solutions_by_component.clear()
        self.safe_cells.clear()
        self.flag_cells.clear()
        self.reducer_result = None

    def _execute_csp(self, pipeline_result: PropagatorPipelineResult) -> None:
        self.segmentation = Segmentation(self.view)
        self.csp = CSPSolver(self.view)

        if self.use_stability and self.stability:
            eligible_components = self.stability.determine_eligible_components(
                self.segmentation,
                pipeline_result.progress_cells(),
            )
        else:
            eligible_components = {component.id for component in self.segmentation.components}

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

        # Overlays post-CSP déclenchés à la demande (avec actions finales)
        # -> voir emit_solver_overlays(actions)

    # ------------------------------------------------------------------
    # Overlays (optionnels)
    # ------------------------------------------------------------------
    def emit_states_overlay(self) -> None:
        cfg = self.overlay_metadata or {}
        screenshot = cfg.get("screenshot_path")
        bounds = cfg.get("bounds")
        stride = cfg.get("stride")
        cell_size = cfg.get("cell_size")
        export_root = cfg.get("export_root")
        if not (screenshot and bounds and stride and cell_size and export_root):
            return

        classification = FrontierClassifier(self.cells).classify()
        frontier = set(classification.frontier)
        active = set(classification.active)
        solved = set(classification.solved)

        try:
            render_states_overlay(
                Path(screenshot),
                bounds,
                active=active,
                frontier=frontier,
                solved=solved,
                stride=stride,
                cell_size=cell_size,
                export_root=export_root,
                suffix="pre",
            )
        except Exception:
            pass

    def emit_solver_overlays(self, actions: List[SolverAction]) -> None:
        cfg = self.overlay_metadata or {}
        screenshot = cfg.get("screenshot_path")
        bounds = cfg.get("bounds")
        stride = cfg.get("stride")
        cell_size = cfg.get("cell_size")
        export_root = cfg.get("export_root")
        if not (screenshot and bounds and stride and cell_size and export_root):
            return
        reducer_actions: List[SolverAction] = []
        if self.reducer_result:
            reducer_actions.extend(
                SolverAction(cell=c, type=SolverActionType.CLICK, confidence=1.0, reasoning="reducer")
                for c in self.reducer_result.safe_cells
            )
            reducer_actions.extend(
                SolverAction(cell=c, type=SolverActionType.FLAG, confidence=1.0, reasoning="reducer")
                for c in self.reducer_result.flag_cells
            )

        # Segmentation overlay
        try:
            if self.segmentation:
                render_segmentation_overlay(
                    Path(screenshot),
                    bounds,
                    segmentation=self.segmentation,
                    stride=stride,
                    cell_size=cell_size,
                    export_root=export_root,
                )
        except Exception:
            pass

        # Actions + combiné overlays
        if actions or reducer_actions:
            try:
                classification = FrontierClassifier(self.cells).classify()
                active_coords = set(classification.active)
                frontier_coords = set(classification.frontier)
                solved_coords = set(classification.solved)
                render_actions_overlay(
                    Path(screenshot),
                    bounds,
                    reducer_actions=reducer_actions,
                    csp_actions=actions,
                    stride=stride,
                    cell_size=cell_size,
                    export_root=export_root,
                )
                render_combined_overlay(
                    Path(screenshot),
                    bounds,
                    actions=actions,
                    zones=(
                        active_coords,
                        frontier_coords,
                        solved_coords,
                    ),
                    cells=self.cells,
                    stride=stride,
                    cell_size=cell_size,
                    export_root=export_root,
                    reducer_actions=reducer_actions,
                )
            except Exception:
                pass

    def _build_best_guess_action(self) -> SolverAction | None:
        """Construit une action GUESS à partir des probabilités par zone (plus faible probabilité)."""
        if not self.segmentation or not self.zone_probabilities:
            return None
        best_prob = 1.1
        best_cell: Coord | None = None
        for zone in self.segmentation.zones:
            prob = self.zone_probabilities.get(zone.id)
            if prob is None:
                continue
            if 1e-6 < prob < best_prob and zone.cells:
                best_prob = prob
                best_cell = zone.cells[0]
        if best_cell:
            return SolverAction(
                cell=best_cell,
                type=SolverActionType.GUESS,
                confidence=1.0,
                reasoning=f"best-guess p={best_prob:.3f}",
            )
        return None

    def _apply_reducer_actions(self, reducer_result: PropagationResult) -> None:
        updated = False
        for coord in reducer_result.safe_cells:
            cell = self.cells.get(coord)
            if cell and cell.logical_state == LogicalCellState.UNREVEALED:
                self.cells[coord] = replace(
                    cell,
                    logical_state=LogicalCellState.EMPTY,
                    solver_status=SolverStatus.SOLVED,
                )
                updated = True
        for coord in reducer_result.flag_cells:
            cell = self.cells.get(coord)
            if cell and cell.logical_state != LogicalCellState.CONFIRMED_MINE:
                self.cells[coord] = replace(
                    cell,
                    logical_state=LogicalCellState.CONFIRMED_MINE,
                    solver_status=SolverStatus.SOLVED,
                )
                updated = True

        if updated:
            classifier = FrontierClassifier(self.cells)
            zones = classifier.classify()
            self.view = SolverFrontierView(self.cells, set(zones.frontier))

    def _build_pipeline_stub(
        self,
        reducer_result: PropagationResult,
    ) -> PropagatorPipelineResult:
        def _blank(reason: str) -> PropagationResult:
            return PropagationResult(set(), set(), set(), 0, reason)

        return PropagatorPipelineResult(
            safe_cells=reducer_result.safe_cells,
            flag_cells=reducer_result.flag_cells,
            iterative=reducer_result,
            subset=_blank("subset-skip"),
            advanced=_blank("advanced-skip"),
            iterative_refresh=_blank("iter-refresh-skip"),
        )
