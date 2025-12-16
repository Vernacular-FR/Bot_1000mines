from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from src.lib.s3_storage.facade import GridCell, LogicalCellState
from ..s40_states_analyzer.grid_classifier import FrontierClassifier
from .s411_frontiere_reducer import PropagationResult


Coord = Tuple[int, int]


@dataclass(frozen=True)
class Constraint:
    vars: frozenset[Coord]
    count: int
    sources: frozenset[Coord]


class SubsetConstraintPropagator:
    """
    Propagation par inclusion de contraintes (phase 1.5).

    - Construit des contraintes normalisées pour chaque cellule ACTIVE.
    - Applique la règle générique: si C1.vars ⊆ C2.vars alors Cdiff = C2 - C1.
    - Déduit de nouvelles cases SAFE / FLAG sans recourir à un CSP complet.
    """

    def __init__(self, cells: Dict[Coord, GridCell]) -> None:
        self.cells = cells
        self.simulated_states: Dict[Coord, LogicalCellState] = {}
        self.neighbors_cache: Dict[Coord, List[Coord]] = {}
        self._precompute_neighbors()

    def _precompute_neighbors(self) -> None:
        for coord in self.cells:
            self.neighbors_cache[coord] = [
                (coord[0] + dx, coord[1] + dy)
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                if not (dx == 0 and dy == 0)
                and (coord[0] + dx, coord[1] + dy) in self.cells
            ]

    def _get_logical_state(self, coord: Coord) -> LogicalCellState:
        if coord in self.simulated_states:
            return self.simulated_states[coord]
        return self.cells[coord].logical_state

    def _get_effective_value(self, coord: Coord) -> int:
        cell = self.cells[coord]
        if cell.number_value is None:
            return 0

        confirmed_mines = sum(
            1
            for n in self.neighbors_cache.get(coord, [])
            if self._get_logical_state(n) == LogicalCellState.CONFIRMED_MINE
        )
        return cell.number_value - confirmed_mines

    def _get_closed_neighbors(self, coord: Coord) -> List[Coord]:
        return [
            n
            for n in self.neighbors_cache.get(coord, [])
            if self._get_logical_state(n) == LogicalCellState.UNREVEALED
        ]

    def apply_known_actions(
        self,
        safe_cells: Iterable[Coord] | None = None,
        flag_cells: Iterable[Coord] | None = None,
    ) -> None:
        for coord in safe_cells or ():
            if coord in self.cells:
                self.simulated_states[coord] = LogicalCellState.EMPTY
        for coord in flag_cells or ():
            if coord in self.cells:
                self.simulated_states[coord] = LogicalCellState.CONFIRMED_MINE

    def _build_constraints(self, active_cells: Iterable[Coord]) -> Dict[frozenset[Coord], Constraint]:
        constraints: Dict[frozenset[Coord], Constraint] = {}
        for coord in active_cells:
            cell = self.cells.get(coord)
            if (
                not cell
                or cell.logical_state != LogicalCellState.OPEN_NUMBER
                or cell.number_value is None
            ):
                continue

            closed_neighbors = self._get_closed_neighbors(coord)
            if not closed_neighbors:
                continue

            vars_set = frozenset(closed_neighbors)
            effective_value = self._get_effective_value(coord)
            if effective_value < 0 or effective_value > len(vars_set):
                continue

            constraint = Constraint(vars=vars_set, count=effective_value, sources=frozenset({coord}))
            # Si une contrainte identique existe déjà, on conserve celle avec la valeur la plus restrictive
            existing = constraints.get(vars_set)
            if existing is None or constraint.count < existing.count:
                constraints[vars_set] = constraint
        return constraints

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

        def mark_safe(coord: Coord, sources: frozenset[Coord]) -> None:
            if self._get_logical_state(coord) != LogicalCellState.UNREVEALED:
                return
            self.simulated_states[coord] = LogicalCellState.EMPTY
            if coord in frontier_cells:
                safe_cells.add(coord)
            solved_cells.update(sources)
            reasoning_parts.append(f"Subset inference SAFE {coord} via {sorted(sources)}")

        def mark_flag(coord: Coord, sources: frozenset[Coord]) -> None:
            if self._get_logical_state(coord) != LogicalCellState.UNREVEALED:
                return
            self.simulated_states[coord] = LogicalCellState.CONFIRMED_MINE
            if coord in frontier_cells:
                flag_cells.add(coord)
            solved_cells.update(sources)
            reasoning_parts.append(f"Subset inference FLAG {coord} via {sorted(sources)}")

        state_changed = True
        iterations = 0

        while state_changed:
            iterations += 1
            state_changed = False
            constraints = self._build_constraints(active_cells)
            if not constraints:
                break

            seen = dict(constraints)
            worklist: List[Constraint] = list(seen.values())

            while worklist:
                current = worklist.pop()
                for other in list(seen.values()):
                    if current is other:
                        continue

                    for small, large in ((current, other), (other, current)):
                        if small.vars == large.vars:
                            continue
                        if not small.vars.issubset(large.vars):
                            continue

                        diff_vars = large.vars.difference(small.vars)
                        if not diff_vars:
                            continue
                        diff_count = large.count - small.count
                        if diff_count < 0 or diff_count > len(diff_vars):
                            continue

                        if diff_count == 0:
                            for coord in diff_vars:
                                mark_safe(coord, large.sources.union(small.sources))
                            state_changed = True
                            break
                        if diff_count == len(diff_vars):
                            for coord in diff_vars:
                                mark_flag(coord, large.sources.union(small.sources))
                            state_changed = True
                            break

                        new_vars = frozenset(diff_vars)
                        if diff_count == 0 or diff_count > len(new_vars):
                            continue
                        if new_vars not in seen:
                            new_constraint = Constraint(
                                vars=new_vars,
                                count=diff_count,
                                sources=large.sources.union(small.sources),
                            )
                            seen[new_vars] = new_constraint
                            worklist.append(new_constraint)
                if state_changed:
                    break

            if state_changed:
                # Retirer des actifs les cellules déjà résolues
                active_cells.difference_update(solved_cells)

        reasoning = (
            "; ".join(reasoning_parts)
            if reasoning_parts
            else f"No subset deduction after {iterations} iterations"
        )

        return PropagationResult(
            safe_cells=safe_cells,
            flag_cells=flag_cells,
            solved_cells=solved_cells,
            iterations=iterations,
            reasoning=reasoning,
        )
