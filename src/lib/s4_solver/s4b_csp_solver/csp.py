"""Solveur CSP par backtracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Tuple

from src.lib.s3_storage.types import Coord, LogicalCellState
from .segmentation import Component, Zone


class GridAnalyzerProtocol(Protocol):
    """Interface minimale pour le solveur CSP."""

    FLAG: int
    UNKNOWN: int

    def get_cell(self, x: int, y: int) -> Optional[int]:
        ...


class Solution:
    """Solution trouvée pour une composante."""

    def __init__(self, zone_assignment: Dict[int, int]):
        self.zone_assignment = zone_assignment  # ZoneID -> NumMines

    def get_prob_weight(self, zones: List[Zone]) -> float:
        """Calcule le poids combinatoire C(n, k) pour chaque zone."""
        weight = 1.0
        for zone in zones:
            if zone.id in self.zone_assignment:
                k = self.zone_assignment[zone.id]
                n = len(zone.cells)
                weight *= self._combinations(n, k)
        return weight

    def _combinations(self, n: int, k: int) -> int:
        if k < 0 or k > n:
            return 0
        if k == 0 or k == n:
            return 1
        if k > n // 2:
            k = n - k
        res = 1
        for i in range(k):
            res = res * (n - i) // (i + 1)
        return res


@dataclass
class ConstraintModel:
    """Modèle de contrainte pour le backtracking."""

    def __init__(self, limit: int, zone_ids: List[int]):
        self.limit = limit
        self.zone_ids = zone_ids
        self.current_sum = 0
        self.assigned_count = 0


class CSPSolver:
    """Solveur CSP par backtracking sur les composantes."""

    def __init__(self, analyzer: GridAnalyzerProtocol):
        self.analyzer = analyzer
        self.solutions: List[Solution] = []

    def solve_component(self, component: Component) -> List[Solution]:
        """Résout une composante et retourne toutes les solutions valides."""
        self.solutions = []

        zone_to_constraints: Dict[int, List[ConstraintModel]] = {}

        for c_coord in component.constraints:
            cell_val = self.analyzer.get_cell(*c_coord)

            if cell_val is None or cell_val < 0:
                continue

            neighbors = list(self._get_neighbors(c_coord[0], c_coord[1]))
            relevant_zones = []
            flags = 0

            for nx, ny in neighbors:
                n_val = self.analyzer.get_cell(nx, ny)
                if n_val == self.analyzer.FLAG:
                    flags += 1
                elif n_val == self.analyzer.UNKNOWN:
                    for zone in component.zones:
                        if (nx, ny) in zone.cells:
                            if zone.id not in relevant_zones:
                                relevant_zones.append(zone.id)
                            break

            effective_limit = cell_val - flags

            if effective_limit < 0:
                return []

            model = ConstraintModel(limit=effective_limit, zone_ids=relevant_zones)

            for zone_id in relevant_zones:
                if zone_id not in zone_to_constraints:
                    zone_to_constraints[zone_id] = []
                zone_to_constraints[zone_id].append(model)

        if not zone_to_constraints:
            return []

        domains: Dict[int, List[int]] = {}
        for zone_id in zone_to_constraints.keys():
            zone = next(z for z in component.zones if z.id == zone_id)
            domains[zone_id] = list(range(len(zone.cells) + 1))

        zones_sorted = sorted(zone_to_constraints.keys())
        self._backtrack({}, zones_sorted, domains, zone_to_constraints)

        return self.solutions

    def _backtrack(
        self,
        assignment: Dict[int, int],
        unassigned: List[int],
        domains: Dict[int, List[int]],
        zone_to_constraints: Dict[int, List[ConstraintModel]],
    ) -> None:
        if not unassigned:
            self.solutions.append(Solution(assignment.copy()))
            return

        var = unassigned[0]
        rest = unassigned[1:]

        for val in domains[var]:
            valid = True

            affected_constraints = zone_to_constraints.get(var, [])
            updated_constraints = []

            for c in affected_constraints:
                c.current_sum += val
                c.assigned_count += 1
                updated_constraints.append(c)

                if c.current_sum > c.limit:
                    valid = False
                elif c.assigned_count == len(c.zone_ids) and c.current_sum != c.limit:
                    valid = False

                if not valid:
                    break

            if valid:
                assignment[var] = val
                self._backtrack(assignment, rest, domains, zone_to_constraints)
                del assignment[var]

            for c in updated_constraints:
                c.current_sum -= val
                c.assigned_count -= 1

    def _get_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        neighbors: List[Tuple[int, int]] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self.analyzer.get_cell(nx, ny) is not None:
                    neighbors.append((nx, ny))
        return neighbors
