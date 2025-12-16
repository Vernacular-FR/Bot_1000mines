from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from src.lib.s3_storage.facade import GridCell, LogicalCellState
from ..s40_states_analyzer.grid_classifier import FrontierClassifier
from .s411_frontiere_reducer import PropagationResult
from .s412_subset_constraint_propagator import Constraint, SubsetConstraintPropagator


Coord = Tuple[int, int]


@dataclass(frozen=True)
class PairwiseContext:
    first: Constraint
    second: Constraint
    common: frozenset[Coord]
    only_first: frozenset[Coord]
    only_second: frozenset[Coord]


MAX_VARS_PER_CONSTRAINT = 6


class AdvancedConstraintEngine(SubsetConstraintPropagator):
    """
    Phase 3 : propagation avancée (inclusions partielles + pairwise elimination).

    - Compare les contraintes deux à deux pour exploiter les intersections partielles.
    - Force des cases SAFE/FLAG quand les bornes deviennent triviales.
    - Reste purement déterministe et limité à de petits ensembles (|vars| <= 6).
    """

    def solve_with_zones(self, zones=None) -> PropagationResult:
        if zones is None:
            classifier = FrontierClassifier(self.cells)
            zones = classifier.classify()

        active_cells: Set[Coord] = set(zones.active)
        frontier_cells: Set[Coord] = set(zones.frontier)

        safe_cells: Set[Coord] = set()
        flag_cells: Set[Coord] = set()
        solved_cells: Set[Coord] = set()
        reasoning_parts: List[str] = []

        def mark_safe(coord: Coord, sources: frozenset[Coord], reason: str) -> bool:
            if self._get_logical_state(coord) != LogicalCellState.UNREVEALED:
                return False
            self.simulated_states[coord] = LogicalCellState.EMPTY
            if coord in frontier_cells:
                safe_cells.add(coord)
            solved_cells.update(sources)
            reasoning_parts.append(reason)
            return True

        def mark_flag(coord: Coord, sources: frozenset[Coord], reason: str) -> bool:
            if self._get_logical_state(coord) != LogicalCellState.UNREVEALED:
                return False
            self.simulated_states[coord] = LogicalCellState.CONFIRMED_MINE
            if coord in frontier_cells:
                flag_cells.add(coord)
            solved_cells.update(sources)
            reasoning_parts.append(reason)
            return True

        def mark_group(group: Iterable[Coord], sources: frozenset[Coord], flag: bool, label: str) -> bool:
            changed_locally = False
            for coord in group:
                if flag:
                    changed_locally |= mark_flag(coord, sources, f"{label} FLAG {coord} via {sorted(sources)}")
                else:
                    changed_locally |= mark_safe(coord, sources, f"{label} SAFE {coord} via {sorted(sources)}")
            return changed_locally

        iterations = 0
        state_changed = True

        while state_changed:
            iterations += 1
            state_changed = False
            constraints_map = {
                vars_set: constraint
                for vars_set, constraint in self._build_constraints(active_cells).items()
                if len(vars_set) <= MAX_VARS_PER_CONSTRAINT
            }
            if not constraints_map:
                break

            var_index = defaultdict(list)
            for constraint in constraints_map.values():
                for var in constraint.vars:
                    var_index[var].append(constraint)

            processed_pairs: Set[Tuple[int, int]] = set()
            for constraints_list in var_index.values():
                for idx in range(len(constraints_list)):
                    c1 = constraints_list[idx]
                    for jdx in range(idx + 1, len(constraints_list)):
                        c2 = constraints_list[jdx]
                        key = tuple(sorted((id(c1), id(c2))))
                        if key in processed_pairs:
                            continue
                        processed_pairs.add(key)

                        ctx = self._build_pairwise_context(c1, c2)
                        if ctx is None or not ctx.common:
                            continue

                        sources = c1.sources.union(c2.sources)
                        changed = self._process_pairwise_context(
                            ctx,
                            sources,
                            mark_group,
                        )
                        if changed:
                            state_changed = True

            if state_changed:
                active_cells.difference_update(solved_cells)

        reasoning = (
            "; ".join(reasoning_parts)
            if reasoning_parts
            else f"No advanced deduction after {iterations} iterations"
        )

        return PropagationResult(
            safe_cells=safe_cells,
            flag_cells=flag_cells,
            solved_cells=solved_cells,
            iterations=iterations,
            reasoning=reasoning,
        )

    def _build_pairwise_context(self, c1: Constraint, c2: Constraint) -> PairwiseContext | None:
        common = frozenset(c1.vars.intersection(c2.vars))
        if not common:
            return None
        only_first = frozenset(c1.vars.difference(common))
        only_second = frozenset(c2.vars.difference(common))
        return PairwiseContext(
            first=c1,
            second=c2,
            common=common,
            only_first=only_first,
            only_second=only_second,
        )

    def _process_pairwise_context(
        self,
        ctx: PairwiseContext,
        sources: frozenset[Coord],
        mark_group,
    ) -> bool:
        changed = False

        c1 = ctx.first
        c2 = ctx.second
        common = ctx.common
        only1 = ctx.only_first
        only2 = ctx.only_second

        k1 = c1.count
        k2 = c2.count

        len_common = len(common)
        len_only1 = len(only1)
        len_only2 = len(only2)

        # Bornes sur le nombre de mines partagées
        common_min = max(0, k1 - len_only1, k2 - len_only2)
        common_max = min(len_common, k1, k2)
        if common_min > common_max:
            return False  # Contradiction théorique, ignorer

        if len_common > 0 and common_min == common_max:
            if common_min == 0:
                changed |= mark_group(common, sources, flag=False, label="Pairwise common")
            elif common_min == len_common:
                changed |= mark_group(common, sources, flag=True, label="Pairwise common")

        # Bornes sur les parties exclusives
        only1_min = max(0, k1 - common_max)
        only1_max = min(len_only1, k1 - common_min)
        if len_only1 > 0 and only1_min == only1_max:
            if only1_min == 0:
                changed |= mark_group(only1, sources, flag=False, label="Pairwise only1")
            elif only1_min == len_only1:
                changed |= mark_group(only1, sources, flag=True, label="Pairwise only1")

        only2_min = max(0, k2 - common_max)
        only2_max = min(len_only2, k2 - common_min)
        if len_only2 > 0 and only2_min == only2_max:
            if only2_min == 0:
                changed |= mark_group(only2, sources, flag=False, label="Pairwise only2")
            elif only2_min == len_only2:
                changed |= mark_group(only2, sources, flag=True, label="Pairwise only2")

        # Cas particuliers : ensembles unitaires directement forçables
        if len_only1 == 1 and common_min == common_max:
            remaining = k1 - common_min
            coord = next(iter(only1))
            if remaining == 0:
                changed |= mark_group([coord], sources, flag=False, label="Singleton only1")
            elif remaining == 1:
                changed |= mark_group([coord], sources, flag=True, label="Singleton only1")

        if len_only2 == 1 and common_min == common_max:
            remaining = k2 - common_min
            coord = next(iter(only2))
            if remaining == 0:
                changed |= mark_group([coord], sources, flag=False, label="Singleton only2")
            elif remaining == 1:
                changed |= mark_group([coord], sources, flag=True, label="Singleton only2")

        return changed
