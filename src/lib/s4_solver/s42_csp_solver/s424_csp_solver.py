from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Tuple

from .s422_segmentation import Component, Zone

LIMIT_ENUM = 20  # Aligné avec PLAN_S4_SOLVER


class GridAnalyzerProtocol(Protocol):
    """Interface minimale attendue par le solveur CSP."""

    FLAG: int
    UNKNOWN: int

    def get_cell(self, x: int, y: int) -> Optional[int]:
        ...


class Solution:
    def __init__(self, zone_assignment: Dict[int, int]):
        self.zone_assignment = zone_assignment  # ZoneID -> NumMines
    
    def get_prob_weight(self, zones: List[Zone]) -> float:
        """
        Calcule le poids combinatoire de cette solution.
        C'est le produit des C(n, k) pour chaque zone.
        """
        weight = 1.0
        for zone in zones:
            if zone.id in self.zone_assignment:
                k = self.zone_assignment[zone.id]  # Mines placées
                n = len(zone.cells)  # Taille de la zone
                weight *= self._combinations(n, k)
        return weight

    def _combinations(self, n: int, k: int) -> int:
        """Calcule C(n, k)"""
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
    """Modèle interne optimisé pour le backtracking"""
    def __init__(self, limit: int, zone_ids: List[int]):
        self.limit = limit
        self.zone_ids = zone_ids
        self.current_sum = 0
        self.assigned_count = 0  # Combien de zones liées sont assignées


class CSPSolver:
    def __init__(self, analyzer: GridAnalyzerProtocol):
        self.analyzer = analyzer
        self.solutions: List[Solution] = []

    def solve_component(self, component: Component) -> List[Solution]:
        self.solutions = []
        
        # Préparer les modèles de contraintes
        zone_to_constraints: Dict[int, List[ConstraintModel]] = {}
        
        for c_coord in component.constraints:
            cell_val = self.analyzer.get_cell(*c_coord)
            
            if cell_val is None or cell_val < 0:
                continue
                
            # Compter les flags voisins et identifier les zones concernées
            neighbors = list(self._get_neighbors(c_coord[0], c_coord[1]))
            relevant_zones = []
            flags = 0
            
            for nx, ny in neighbors:
                n_val = self.analyzer.get_cell(nx, ny)
                if n_val == self.analyzer.FLAG:
                    flags += 1
                elif n_val == self.analyzer.UNKNOWN:
                    # Trouver la zone pour cette cellule inconnue
                    for zone in component.zones:
                        if (nx, ny) in zone.cells:
                            if zone.id not in relevant_zones:
                                relevant_zones.append(zone.id)
                            break
            
            effective_limit = cell_val - flags
            
            if effective_limit < 0:
                return []
                
            # Créer le modèle de contrainte
            model = ConstraintModel(limit=effective_limit, zone_ids=relevant_zones)
            
            for zone_id in relevant_zones:
                if zone_id not in zone_to_constraints:
                    zone_to_constraints[zone_id] = []
                zone_to_constraints[zone_id].append(model)
        
        # Lancer le backtracking
        if not zone_to_constraints:
            return []
        
        # Préparer les domaines pour chaque zone (0 à taille de la zone)
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
        # Base case: Success
        if not unassigned:
            self.solutions.append(Solution(assignment.copy()))
            return

        # Select var
        var = unassigned[0]
        rest = unassigned[1:]
        
        # Try values
        for val in domains[var]:
            # Check consistency
            valid = True
            
            # Mise à jour temporaire des contraintes impactées
            affected_constraints = zone_to_constraints.get(var, [])
            updated_constraints = []
            
            for c in affected_constraints:
                c.current_sum += val
                c.assigned_count += 1
                updated_constraints.append(c)
                
                # Check 1: Overfill
                if c.current_sum > c.limit:
                    valid = False
                
                # Check 2: Underfill impossible
                # Si on a assigné toutes les zones de cette contrainte
                # et que la somme n'est pas atteinte
                elif c.assigned_count == len(c.zone_ids) and c.current_sum != c.limit:
                    valid = False
                
                if not valid:
                    break # Stop checking constraints for this value
            
            if valid:
                # Continue recursion
                assignment[var] = val
                self._backtrack(assignment, rest, domains, zone_to_constraints)
                del assignment[var]
                
            # Backtrack / Cleanup (Always revert changes made in this iteration)
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


def combinations(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    if k > n // 2:
        k = n - k
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result
