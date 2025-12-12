from __future__ import annotations

from typing import Dict, List, Set, Tuple

from src.lib.s4_solver.core import CSPSolver, Segmentation, SolverFrontierView
from src.lib.s4_solver.core.frontier_reducer import ConstraintReducer
from src.lib.s4_solver.core.pattern_engine import PatternEngine
from src.lib.s3_storage.facade import Coord, GridCell


class HybridSolver:
    """
    Orchestrateur 2-parties :
    1. Résolution par motifs (PatternEngine)
    2. Segmentation des zones + résolution CSP
    3. Probabilités par zone + actions
    """

    def __init__(self, view: SolverFrontierView, cells: Dict[Coord, GridCell]):
        self.view = view
        self.cells = cells  # Store raw cells for PatternEngine
        self.segmentation = Segmentation(view)
        self.csp = CSPSolver(view)
        self.zone_probabilities: Dict[int, float] = {}
        self.solutions_by_component: Dict[int, List] = {}
        self.constraint_safe_cells: Set[Tuple[int, int]] = set()
        self.constraint_flag_cells: Set[Tuple[int, int]] = set()
        self.pattern_safe_cells: Set[Tuple[int, int]] = set()
        self.pattern_flag_cells: Set[Tuple[int, int]] = set()

    def solve(self) -> None:
        self.zone_probabilities.clear()
        self.solutions_by_component.clear()
        self.constraint_safe_cells.clear()
        self.constraint_flag_cells.clear()
        self.pattern_safe_cells.clear()
        self.pattern_flag_cells.clear()

        # Étape 0: Réduction déterministe des contraintes
        constraint_reducer = ConstraintReducer(self.cells)
        constraint_result = constraint_reducer.reduce()
        self.constraint_safe_cells = constraint_result.safe_cells
        self.constraint_flag_cells = constraint_result.flag_cells

        # Étape 1: Résolution par motifs
        pattern_engine = PatternEngine(
            self.cells,
            inferred_flags=self.constraint_flag_cells,
        )
        pattern_result = pattern_engine.solve_patterns()
        self.pattern_safe_cells = pattern_result.safe_cells
        self.pattern_flag_cells = pattern_result.flag_cells
        
        total_safe = len(self.constraint_safe_cells) + len(self.pattern_safe_cells)
        total_flags = len(self.constraint_flag_cells) + len(self.pattern_flag_cells)
        print(f"[PATTERN] Found {total_safe} safe cells, {total_flags} flag cells")
        if pattern_result.reasoning:
            print(f"[PATTERN] Reasoning: {pattern_result.reasoning}")

        # Étape 2: Segmentation et CSP sur les cellules restantes
        for component in self.segmentation.components:
            solutions = self.csp.solve_component(component)
            self.solutions_by_component[component.id] = solutions
            
            if not solutions:
                continue
            
            # Calculer les probabilités par zone
            total_weight = 0.0
            zone_weighted_mines: Dict[int, float] = {z.id: 0.0 for z in component.zones}
            
            for sol in solutions:
                weight = sol.get_prob_weight(self.segmentation.zones)
                total_weight += weight
                
                for zid, mines in sol.zone_assignment.items():
                    zone_weighted_mines[zid] += mines * weight
            
            # Normaliser
            if total_weight > 0:
                for z in component.zones:
                    # Espérance du nombre de mines dans la zone
                    expected_mines = zone_weighted_mines[z.id] / total_weight
                    
                    # Probabilité qu'une cellule spécifique de la zone soit une mine
                    # P(Cell) = E[Mines] / Size
                    prob = expected_mines / len(z.cells)
                    self.zone_probabilities[z.id] = prob

    def get_safe_cells(self) -> List[Tuple[int, int]]:
        """Retourne les cellules sûres trouvées par réduction + motifs + CSP."""
        safe: List[Tuple[int, int]] = []

        safe.extend(self.constraint_safe_cells)
        safe.extend(self.pattern_safe_cells)

        for zone in self.segmentation.zones:
            prob = self.zone_probabilities.get(zone.id)
            if prob is not None and prob < 1e-6:
                safe.extend(zone.cells)
        
        return safe

    def get_flag_cells(self) -> List[Tuple[int, int]]:
        """Retourne les cellules à marquer trouvées par réduction + motifs + CSP."""
        flags: List[Tuple[int, int]] = []

        flags.extend(self.constraint_flag_cells)
        flags.extend(self.pattern_flag_cells)

        for zone in self.segmentation.zones:
            prob = self.zone_probabilities.get(zone.id)
            if prob is not None and prob > 1 - 1e-6:
                flags.extend(zone.cells)
        
        return flags

    def get_best_guess(self) -> Tuple[int, int, float] | None:
        best_prob = 1.1
        best_cell = None
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
