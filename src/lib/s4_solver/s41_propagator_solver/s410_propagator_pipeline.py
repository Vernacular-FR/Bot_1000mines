from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set, Tuple

from src.lib.s3_storage.facade import GridCell
from .s411_frontiere_reducer import IterativePropagator, PropagationResult
from .s412_subset_constraint_propagator import SubsetConstraintPropagator
from .s413_advanced_constraint_engine import AdvancedConstraintEngine

Coord = Tuple[int, int]


@dataclass
class PropagatorPipelineResult:
    safe_cells: Set[Coord]
    flag_cells: Set[Coord]
    iterative: PropagationResult
    subset: PropagationResult
    advanced: PropagationResult
    iterative_refresh: PropagationResult

    @property
    def has_actions(self) -> bool:
        return bool(self.safe_cells or self.flag_cells)

    def progress_cells(self) -> Set[Coord]:
        progress: Set[Coord] = set()
        for result in (self.iterative, self.subset, self.advanced):
            progress.update(result.safe_cells)
            progress.update(result.flag_cells)
            progress.update(result.solved_cells)
        return progress


class PropagatorPipeline:
    """
    Orchestrates phases 1→3 (Iterative, Subset, Advanced) before CSP.

    Reuses the same cell snapshot and simulated states per phase to avoid state divergence.
    """

    def __init__(self, cells: Dict[Coord, GridCell]):
        self.cells = cells

    def run(self) -> PropagatorPipelineResult:
        safe: Set[Coord] = set()
        flag: Set[Coord] = set()

        # Phase 1 – règles locales
        iterative = IterativePropagator(self.cells)
        iterative_result = iterative.solve_with_zones()
        safe.update(iterative_result.safe_cells)
        flag.update(iterative_result.flag_cells)

        # Phase 2 – subset inclusion
        subset = SubsetConstraintPropagator(self.cells)
        subset.apply_known_actions(safe_cells=safe, flag_cells=flag)
        subset_result = subset.solve_with_zones()
        safe.update(subset_result.safe_cells)
        flag.update(subset_result.flag_cells)

        # Phase 3 – pairwise/advanced
        advanced = AdvancedConstraintEngine(self.cells)
        advanced.apply_known_actions(safe_cells=safe, flag_cells=flag)
        advanced_result = advanced.solve_with_zones()
        safe.update(advanced_result.safe_cells)
        flag.update(advanced_result.flag_cells)

        # Phase 4 – re-run local rules to absorb leftovers unlocked by advanced deductions
        iterative_refresh = IterativePropagator(self.cells)
        iterative_refresh.apply_known_actions(safe_cells=safe, flag_cells=flag)
        iterative_refresh_result = iterative_refresh.solve_with_zones()
        safe.update(iterative_refresh_result.safe_cells)
        flag.update(iterative_refresh_result.flag_cells)

        return PropagatorPipelineResult(
            safe_cells=safe,
            flag_cells=flag,
            iterative=iterative_result,
            subset=subset_result,
            advanced=advanced_result,
            iterative_refresh=iterative_refresh_result,
        )
