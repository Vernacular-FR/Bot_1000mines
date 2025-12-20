"""Manager CSP orchestrant reducer + segmentation + solver."""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from src.config import CSP_CONFIG
from src.lib.s3_storage.types import (
    Coord,
    GridCell,
    LogicalCellState,
    SolverStatus,
    ActiveRelevance,
    FrontierRelevance,
)
from src.lib.s4_solver.types import SolverInput, SolverOutput, SolverAction, ActionType
from .reducer import IterativePropagator, PropagationResult
from .segmentation import Segmentation
from .csp import CSPSolver
from .frontier_view import SolverFrontierView


class CspManager:
    """Orchestrateur CSP : reducer + segmentation + backtracking."""

    def __init__(
        self,
        cells: Dict[Coord, GridCell],
        frontier: Set[Coord],
        active_set: Set[Coord],
    ):
        self.cells = cells
        self.frontier = frontier
        self.active_set = active_set
        self.view: SolverFrontierView | None = None
        self.segmentation: Segmentation | None = None
        self.zone_probabilities: Dict[int, float] = {}
        self.solutions_by_component: Dict[int, List] = {}
        self.safe_cells: Set[Coord] = set()
        self.flag_cells: Set[Coord] = set()
        self.reducer_result: PropagationResult | None = None
        self.focus_updates: Dict[Coord, GridCell] = {}

    def run(self, *, bypass_ratio: float | None = None) -> None:
        """Pipeline complet: reducer puis CSP."""
        self._reset_state()

        # Étape 1: Reducer (propagation contrainte)
        print(f"[CSP] Reducer : active={len(self.active_set)}")
        reducer = IterativePropagator(self.cells)
        self.reducer_result = reducer.propagate(self.active_set)
        self._apply_reducer_results()
        print(f"[CSP] Reducer : safe={len(self.reducer_result.safe_cells)}, flag={len(self.reducer_result.flag_cells)}")

        # Bypass CSP si le reducer produit assez d'actions
        if bypass_ratio is not None:
            total_actions = len(self.reducer_result.safe_cells) + len(self.reducer_result.flag_cells)
            if self.frontier and total_actions / len(self.frontier) >= bypass_ratio:
                print("[CSP] Bypass CSP : ratio atteint")
                return

        # Étape 2: CSP exact
        self._execute_csp()

    def _reset_state(self) -> None:
        self.view = None
        self.segmentation = None
        self.zone_probabilities.clear()
        self.solutions_by_component.clear()
        self.safe_cells.clear()
        self.flag_cells.clear()
        self.reducer_result = None
        self.focus_updates = {}

    def _apply_reducer_results(self) -> None:
        """Applique les résultats du reducer."""
        if not self.reducer_result:
            return

        self.safe_cells.update(self.reducer_result.safe_cells)
        self.flag_cells.update(self.reducer_result.flag_cells)

        # Appliquer physiquement les déductions du reducer pour le CSP (flags/mines et safes)
        for coord in self.reducer_result.flag_cells:
            cell = self.cells.get(coord)
            if not cell:
                continue
            self.cells[coord] = replace(
                cell,
                logical_state=LogicalCellState.CONFIRMED_MINE,
                solver_status=SolverStatus.SOLVED,
                focus_level_active=ActiveRelevance.TO_REDUCE,
                focus_level_frontier=FrontierRelevance.TO_PROCESS,
            )

        for coord in self.reducer_result.safe_cells:
            cell = self.cells.get(coord)
            if not cell:
                continue
            # On les sort de la frontière en les marquant vides pour le CSP
            self.cells[coord] = replace(
                cell,
                logical_state=LogicalCellState.EMPTY,
                solver_status=SolverStatus.TO_VISUALIZE,
                focus_level_active=ActiveRelevance.TO_REDUCE,
                focus_level_frontier=FrontierRelevance.TO_PROCESS,
            )

        # Marquer les actives comme REDUCED (focus) et SOLVED (statut)
        for coord in self.reducer_result.solved_cells:
            cell = self.cells.get(coord)
            if cell and cell.solver_status == SolverStatus.ACTIVE:
                self.focus_updates[coord] = replace(
                    cell,
                    solver_status=SolverStatus.SOLVED,
                    focus_level_active=ActiveRelevance.REDUCED,
                )

    def _execute_csp(self) -> None:
        """Exécute le CSP solver sur la frontière."""
        # Recalculer la frontière après le reducer en partant de celle du storage
        working_frontier = self._compute_working_frontier(self.frontier)
        if not working_frontier:
            print("[CSP] Frontière vide après reducer")
            return

        print(f"[CSP] Segmentation : frontier={len(working_frontier)}")
        self.view = SolverFrontierView(self.cells, working_frontier)
        self.segmentation = Segmentation(self.view)
        print(f"[CSP] Composantes : {len(self.segmentation.components)}, zones={len(self.segmentation.zones)}")

        csp = CSPSolver(self.view)
        
        # Limite de sécurité : skip les composantes trop grandes (évite explosion backtracking)
        max_zones = CSP_CONFIG['max_zones_per_component']

        for idx, component in enumerate(self.segmentation.components):
            num_zones = len(component.zones)
            total_cells = sum(len(z.cells) for z in component.zones)
            
            if num_zones > max_zones:
                print(f"[CSP] SKIP composante {idx+1} : trop grande ({num_zones} zones > {max_zones})")
                continue
            
            solutions = csp.solve_component(component)
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
                if not zone.cells:
                    continue
                prob = (zone_weighted_mines[zone.id] / total_weight) / len(zone.cells)
                self.zone_probabilities[zone.id] = prob

                if prob < 1e-6:
                    self.safe_cells.update(zone.cells)
                elif prob > 1 - 1e-6:
                    self.flag_cells.update(zone.cells)

        print(f"[CSP] Résultat final : safe={len(self.safe_cells)}, flag={len(self.flag_cells)}")
        # Marquer les zones traitées comme PROCESSED
        self._mark_processed_frontier()

    def _compute_working_frontier(self, source_frontier: Set[Coord] | None = None) -> Set[Coord]:
        """Calcule la frontière de travail à partir du storage ou par détection locale."""
        frontier = set(source_frontier or [])
        # Nettoyer et compléter : uniquement UNREVEALED encore non résolues
        frontier = {
            coord for coord in frontier
            if coord in self.cells
            and self.cells[coord].logical_state == LogicalCellState.UNREVEALED
            and coord not in self.safe_cells
            and coord not in self.flag_cells
        }

        # Si aucune frontière fournie, déduire depuis les OPEN_NUMBER voisins
        for coord, cell in self.cells.items():
            if cell.logical_state != LogicalCellState.UNREVEALED:
                continue
            if coord in self.safe_cells or coord in self.flag_cells:
                continue
            # Vérifier si adjacent à une cellule numérotée
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = coord[0] + dx, coord[1] + dy
                    neighbor = self.cells.get((nx, ny))
                    if neighbor and neighbor.logical_state == LogicalCellState.OPEN_NUMBER:
                        frontier.add(coord)
                        break
                else:
                    continue
                break
        return frontier

    def _mark_processed_frontier(self) -> None:
        """Marque les cellules frontière traitées par le CSP."""
        if not self.segmentation:
            return

        for component in self.segmentation.components:
            for zone in component.zones:
                for coord in zone.cells:
                    cell = self.cells.get(coord)
                    if not cell or cell.solver_status != SolverStatus.FRONTIER:
                        continue
                    self.focus_updates[coord] = replace(
                        cell,
                        focus_level_frontier=FrontierRelevance.PROCESSED,
                    )

    def get_best_guess(self) -> tuple[int, int, float] | None:
        """Retourne la meilleure case à deviner (probabilité minimale)."""
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
            return best_cell[0], best_cell[1], best_prob
        return None


def solve(input: SolverInput, *, allow_guess: bool = False, return_segmentation: bool = False):
    """Résout le démineur via reducer + CSP et retourne les actions (et optionnellement la segmentation)."""
    if not input.cells:
        return SolverOutput(actions=[], metadata={"error": "No cells"})

    # Pipeline complet: Reducer + CSP
    manager = CspManager(input.cells, input.frontier, input.active_set)
    manager.run()

    # Convertir en actions
    actions: List[SolverAction] = []
    reducer_safe = set()
    reducer_flags = set()
    reducer_actions: List[SolverAction] = []

    if manager.reducer_result:
        reducer_safe = manager.reducer_result.safe_cells
        reducer_flags = manager.reducer_result.flag_cells

    # Actions issues du reducer (pour overlay transparent)
    for coord in reducer_safe:
        reducer_actions.append(SolverAction(
            coord=coord,
            action=ActionType.SAFE,
            confidence=1.0,
            reasoning="reducer",
        ))
    for coord in reducer_flags:
        reducer_actions.append(SolverAction(
            coord=coord,
            action=ActionType.FLAG,
            confidence=1.0,
            reasoning="reducer",
        ))

    # Actions finales (incluant celles du CSP)
    for coord in manager.safe_cells:
        reasoning = "reducer" if coord in reducer_safe else "csp"
        actions.append(SolverAction(
            coord=coord,
            action=ActionType.SAFE,
            confidence=1.0,
            reasoning=reasoning,
        ))

    for coord in manager.flag_cells:
        reasoning = "reducer" if coord in reducer_flags else "csp"
        actions.append(SolverAction(
            coord=coord,
            action=ActionType.FLAG,
            confidence=1.0,
            reasoning=reasoning,
        ))

    # Guess si aucune action et autorisé
    if not actions and allow_guess:
        guess = manager.get_best_guess()
        if guess:
            x, y, prob = guess
            actions.append(SolverAction(
                coord=(x, y),
                action=ActionType.GUESS,
                confidence=1.0 - prob,
                reasoning=f"CSP Best Guess ({prob*100:.1f}% mine)",
            ))

    solver_output = SolverOutput(
        actions=actions,
        reducer_actions=reducer_actions,
        metadata={
            "reducer_safe": len(reducer_safe),
            "reducer_flags": len(reducer_flags),
            "csp_safe": len(manager.safe_cells - reducer_safe),
            "csp_flags": len(manager.flag_cells - reducer_flags),
            "zones": len(manager.segmentation.zones) if manager.segmentation else 0,
            "components": len(manager.segmentation.components) if manager.segmentation else 0,
        },
    )

    if return_segmentation:
        return solver_output, manager.segmentation
    return solver_output


def solve_from_cells(
    cells: Dict[Coord, GridCell],
    frontier: Set[Coord] = None,
    active_set: Set[Coord] = None,
    *,
    allow_guess: bool = False,
    return_segmentation: bool = False,
):
    """Wrapper pour résoudre directement depuis un dict de cellules."""
    if frontier is None:
        frontier = set()
    if active_set is None:
        active_set = set()
    
    return solve(
        SolverInput(cells=cells, frontier=frontier, active_set=active_set),
        allow_guess=allow_guess,
        return_segmentation=return_segmentation,
    )
