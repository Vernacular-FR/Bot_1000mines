"""CSP Solver pour les contraintes complexes."""

from typing import Dict, Set, Tuple, List, Optional
from itertools import product

from src.lib.s0_coordinates.types import Coord
from .types import GridCell, SolverAction, ActionType


class CspSolver:
    """Résolution CSP pour les contraintes complexes."""

    def __init__(
        self,
        cells: Dict[Tuple[int, int], GridCell],
        max_component_size: int = 20,
    ):
        self.cells = cells
        self.max_component_size = max_component_size
        self.safe_cells: Set[Tuple[int, int]] = set()
        self.flag_cells: Set[Tuple[int, int]] = set()
        self.probabilities: Dict[Tuple[int, int], float] = {}

    def solve(
        self,
        frontier: Set[Tuple[int, int]],
        active_set: Set[Tuple[int, int]],
        excluded: Optional[Set[Tuple[int, int]]] = None,
    ) -> bool:
        """
        Résout les contraintes CSP.
        Retourne True si des déductions ont été faites.
        """
        excluded = excluded or set()
        remaining_frontier = frontier - excluded
        
        if not remaining_frontier:
            return False

        # Segmentation en composantes connexes
        components = self._segment_frontier(remaining_frontier, active_set)
        
        found_actions = False
        for component in components:
            if len(component) > self.max_component_size:
                continue
            
            # Contraintes pour cette composante
            constraints = self._build_constraints(component, active_set)
            if not constraints:
                continue
            
            # Énumération des solutions
            solutions = self._enumerate_solutions(component, constraints)
            if not solutions:
                continue
            
            # Analyse des solutions
            self._analyze_solutions(component, solutions)
            found_actions = True

        return found_actions

    def get_actions(self) -> List[SolverAction]:
        """Retourne les actions déduites par CSP."""
        actions = []
        
        for coord_tuple in self.safe_cells:
            actions.append(SolverAction(
                coord=Coord(row=coord_tuple[0], col=coord_tuple[1]),
                action=ActionType.CLICK,
                confidence=1.0,
            ))
        
        for coord_tuple in self.flag_cells:
            actions.append(SolverAction(
                coord=Coord(row=coord_tuple[0], col=coord_tuple[1]),
                action=ActionType.FLAG,
                confidence=1.0,
            ))
        
        return actions

    def get_best_guess(self) -> Optional[SolverAction]:
        """Retourne le meilleur guess basé sur les probabilités."""
        if not self.probabilities:
            return None
        
        # Trouve la cellule avec la probabilité de mine la plus basse
        best_coord = min(self.probabilities.keys(), key=lambda c: self.probabilities[c])
        best_prob = self.probabilities[best_coord]
        
        if best_prob >= 1.0:
            return None
        
        return SolverAction(
            coord=Coord(row=best_coord[0], col=best_coord[1]),
            action=ActionType.GUESS,
            confidence=1.0 - best_prob,
            probability=best_prob,
        )

    def _segment_frontier(
        self,
        frontier: Set[Tuple[int, int]],
        active_set: Set[Tuple[int, int]],
    ) -> List[Set[Tuple[int, int]]]:
        """Segmente la frontière en composantes connexes."""
        remaining = set(frontier)
        components = []
        
        while remaining:
            start = next(iter(remaining))
            component = set()
            queue = [start]
            
            while queue:
                cell = queue.pop(0)
                if cell in component:
                    continue
                component.add(cell)
                remaining.discard(cell)
                
                # Trouve les voisins connectés via les contraintes actives
                for active in active_set:
                    active_neighbors = self._get_neighbors(active)
                    if cell in active_neighbors:
                        for neighbor in active_neighbors:
                            if neighbor in remaining and neighbor not in component:
                                queue.append(neighbor)
            
            if component:
                components.append(component)
        
        return components

    def _build_constraints(
        self,
        component: Set[Tuple[int, int]],
        active_set: Set[Tuple[int, int]],
    ) -> List[Tuple[Tuple[int, int], int, List[Tuple[int, int]]]]:
        """Construit les contraintes pour une composante."""
        constraints = []
        
        for active_coord in active_set:
            cell = self.cells.get(active_coord)
            if not cell or not cell.is_number:
                continue
            
            neighbors = [n for n in self._get_neighbors(active_coord) if n in component]
            if not neighbors:
                continue
            
            flagged = sum(1 for n in self._get_neighbors(active_coord) 
                         if self.cells.get(n) and self.cells[n].is_flagged)
            remaining = cell.adjacent_mine_count - flagged
            
            if remaining >= 0:
                constraints.append((active_coord, remaining, neighbors))
        
        return constraints

    def _enumerate_solutions(
        self,
        component: Set[Tuple[int, int]],
        constraints: List[Tuple[Tuple[int, int], int, List[Tuple[int, int]]]],
    ) -> List[Dict[Tuple[int, int], bool]]:
        """Énumère toutes les solutions valides."""
        cells_list = list(component)
        solutions = []
        
        # Limite pour éviter l'explosion combinatoire
        if len(cells_list) > self.max_component_size:
            return []
        
        for assignment in product([False, True], repeat=len(cells_list)):
            config = dict(zip(cells_list, assignment))
            if self._is_valid_config(config, constraints):
                solutions.append(config)
        
        return solutions

    def _is_valid_config(
        self,
        config: Dict[Tuple[int, int], bool],
        constraints: List[Tuple[Tuple[int, int], int, List[Tuple[int, int]]]],
    ) -> bool:
        """Vérifie si une configuration satisfait toutes les contraintes."""
        for _, required_mines, neighbors in constraints:
            mine_count = sum(1 for n in neighbors if config.get(n, False))
            if mine_count != required_mines:
                return False
        return True

    def _analyze_solutions(
        self,
        component: Set[Tuple[int, int]],
        solutions: List[Dict[Tuple[int, int], bool]],
    ) -> None:
        """Analyse les solutions pour déduire safe/flag/probabilités."""
        if not solutions:
            return
        
        for cell in component:
            mine_count = sum(1 for sol in solutions if sol.get(cell, False))
            probability = mine_count / len(solutions)
            self.probabilities[cell] = probability
            
            if probability == 0.0:
                self.safe_cells.add(cell)
            elif probability == 1.0:
                self.flag_cells.add(cell)

    def _get_neighbors(self, coord: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Retourne les 8 voisins d'une cellule."""
        row, col = coord
        neighbors = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                neighbors.append((row + dr, col + dc))
        return neighbors
