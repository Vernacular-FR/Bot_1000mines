from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Set, Tuple, Optional

from src.config import CELL_SIZE, CELL_BORDER

from src.lib.s3_storage.facade import (
    ActiveRelevance,
    Bounds,
    Coord,
    FrontierRelevance,
    GridCell,
    LogicalCellState,
    ActionStatus,
    SolverStatus,
    StorageUpsert,
)
from src.lib.s4_solver.facade import SolverAction, SolverActionType, SolverStats
from src.lib.s4_solver.s40_states_analyzer.grid_extractor import SolverFrontierView
from src.lib.s4_solver.s42_csp_solver.s420_csp_manager import CspManager
from src.lib.s4_solver.s49_cleanup import build_cleanup_actions
from src.lib.s4_solver.s42_csp_solver.s422_segmentation import Segmentation


class OptimizedSolver:
    """
    Orchestrateur CSP optimisé :
    1. FrontiereReducer minimal (intégré dans CspManager)
    2. Segmentation + CSP exact
    3. Probabilités par zone + actions
    """

    def __init__(
        self,
        view: SolverFrontierView,
        cells: Dict[Coord, GridCell],
        overlay_metadata: Optional[Dict] = None,
    ):
        self.view = view
        self.cells = cells
        self.segmentation: Segmentation | None = None
        self.zone_probabilities: Dict[int, float] = {}
        self.solutions_by_component: Dict[int, List] = {}
        self.safe_cells: Set[Tuple[int, int]] = set()
        self.flag_cells: Set[Tuple[int, int]] = set()
        self.csp_manager: CspManager | None = None
        self.overlay_metadata = overlay_metadata

    def solve(self, *, bypass_ratio: float | None = None) -> None:
        self.zone_probabilities.clear()
        self.solutions_by_component.clear()
        self.safe_cells.clear()
        self.flag_cells.clear()
        self.segmentation = None
        self.csp_manager = None

        # Exécuter le pipeline : réduction systématique puis CSP optionnel
        self.csp_manager = CspManager(
            self.view,
            self.cells,
            overlay_metadata=self.overlay_metadata,
        )
        # Overlay d'état initial (pré-CSP) une seule fois
        try:
            self.csp_manager.emit_states_overlay()
        except Exception:
            pass
        self.csp_manager.run_with_frontier_reducer(
            bypass_ratio=bypass_ratio,
        )
        self.segmentation = self.csp_manager.segmentation
        self.solutions_by_component = self.csp_manager.solutions_by_component
        self.zone_probabilities = self.csp_manager.zone_probabilities
        self.safe_cells.update(self.csp_manager.safe_cells)
        self.flag_cells.update(self.csp_manager.flag_cells)
    def emit_overlays(self, actions: List[SolverAction]) -> None:
        """Déclenche les overlays post-CSP avec les actions finales."""
        if not self.csp_manager:
            return
        try:
            self.csp_manager.emit_solver_overlays(actions)
        except Exception:
            pass

    def get_safe_cells(self) -> List[Tuple[int, int]]:
        """Retourne les cellules sûres trouvées par réduction + motifs + CSP."""
        safe = set(self.safe_cells)
        if self.segmentation:
            for zone in self.segmentation.zones:
                prob = self.zone_probabilities.get(zone.id)
                if prob is not None and prob < 1e-6:
                    safe.update(zone.cells)
        return sorted(safe)

    def get_flag_cells(self) -> List[Tuple[int, int]]:
        """Retourne les cellules à marquer trouvées par réduction + motifs + CSP."""
        flags = set(self.flag_cells)
        if self.segmentation:
            for zone in self.segmentation.zones:
                prob = self.zone_probabilities.get(zone.id)
                if prob is not None and prob > 1 - 1e-6:
                    flags.update(zone.cells)
        return sorted(flags)

    def get_best_guess(self) -> Tuple[int, int, float] | None:
        if not self.segmentation:
            return None
        best_prob = 1.1
        best_cell: Tuple[int, int] | None = None
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


@dataclass
class SolverUpdate:
    actions: List[SolverAction]
    cleanup_actions: List[SolverAction]
    stats: SolverStats
    storage_upsert: StorageUpsert
    cleanup_targets: Set[Coord]


Coord = Tuple[int, int]


def compute_bounds(coords: Set[Coord]) -> Bounds:
    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    min_x, max_x = min(xs) - 2, max(xs) + 3
    min_y, max_y = min(ys) - 2, max(ys) + 3
    return (min_x, min_y, max_x, max_y)


def build_metadata_updates(
    cells: Dict[Coord, GridCell],
    frontier_coords: Set[Coord],
    safe_cells: Iterable[Coord],
    flag_cells: Iterable[Coord],
    segmentation: Optional[Segmentation],
) -> Dict[Coord, GridCell]:
    safe_set = set(safe_cells)
    flag_set = set(flag_cells)
    updated: Dict[Coord, GridCell] = {}

    zone_focus: Dict[int, FrontierRelevance] = {}
    if segmentation:
        for zone in segmentation.zones:
            zone_focus[zone.id] = FrontierRelevance.PROCESSED

    for coord, cell in cells.items():
        desired_status = _classify_solver_status(coord, cell, frontier_coords, cells)
        desired_action = cell.action_status
        desired_focus_active = None
        desired_focus_frontier = None
        desired_logical_state = cell.logical_state

        if coord in safe_set:
            desired_status = SolverStatus.TO_VISUALIZE
            desired_action = ActionStatus.SAFE
            desired_focus_active = None
            desired_focus_frontier = None
            desired_logical_state = LogicalCellState.EMPTY
        elif coord in flag_set:
            desired_status = SolverStatus.SOLVED
            desired_action = ActionStatus.FLAG
            desired_focus_active = None
            desired_focus_frontier = None
            desired_logical_state = LogicalCellState.CONFIRMED_MINE
        elif desired_action != ActionStatus.NONE:
            desired_action = ActionStatus.NONE

        if desired_status == SolverStatus.ACTIVE:
            # Cas par défaut : nouvelles ACTIVE (nouvelles infos) → TO_REDUCE
            desired_focus_active = ActiveRelevance.TO_REDUCE
            # Si cette case était déjà traitée lors de la passe précédente, on la marque REDUCED
            if cell.focus_level_active == ActiveRelevance.TO_REDUCE:
                desired_focus_active = ActiveRelevance.REDUCED
            elif cell.focus_level_active == ActiveRelevance.REDUCED:
                desired_focus_active = ActiveRelevance.REDUCED
        if desired_status == SolverStatus.FRONTIER:
            desired_zone_focus = None
            if segmentation:
                zone = segmentation.zone_for_cell(coord)
                if zone is not None:
                    desired_zone_focus = zone_focus.get(zone.id, FrontierRelevance.PROCESSED)
            desired_focus_frontier = desired_zone_focus or FrontierRelevance.TO_PROCESS

        if (
            desired_status != cell.solver_status
            or desired_action != cell.action_status
            or desired_focus_active != cell.focus_level_active
            or desired_focus_frontier != cell.focus_level_frontier
            or desired_logical_state != cell.logical_state
        ):
            updated[coord] = replace(
                cell,
                solver_status=desired_status,
                action_status=desired_action,
                focus_level_active=desired_focus_active,
                focus_level_frontier=desired_focus_frontier,
                topological_state=desired_status,
                logical_state=desired_logical_state,
            )

    return updated


def compute_frontier_from_cells(
    cells: Dict[Coord, GridCell],
) -> Set[Coord]:
    frontier: Set[Coord] = set()
    for (x, y), cell in cells.items():
        if cell.logical_state not in {LogicalCellState.OPEN_NUMBER, LogicalCellState.EMPTY}:
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nb = (x + dx, y + dy)
                nb_cell = cells.get(nb)
                if not nb_cell:
                    continue
                if nb_cell.logical_state == LogicalCellState.UNREVEALED:
                    frontier.add(nb)
    return frontier


def compute_active_remove(
    cells: Dict[Coord, GridCell],
) -> Set[Coord]:
    """
    Retire des ACTIVE toutes les cases qui ne sont plus exploitables localement
    (OPEN_NUMBER sans voisins UNREVEALED) ou qui sont devenues des mines/vides.
    """
    return {
        coord
        for coord, cell in cells.items()
        if cell.logical_state in {
            LogicalCellState.EMPTY,
            LogicalCellState.CONFIRMED_MINE,
        }
        or (
            cell.logical_state == LogicalCellState.OPEN_NUMBER
            and not _has_unrevealed_neighbor(coord, cells)
        )
    }


def compute_solver_update(
    solver: OptimizedSolver,
    cells: Dict[Coord, GridCell],
    frontier_coords: Set[Coord],
    current_frontier_in_bounds: Set[Coord],
    *,
    allow_guess: bool = False,
    enable_cleanup: bool = True,
) -> SolverUpdate:
    safe_cells = set(solver.get_safe_cells())
    flag_cells = set(solver.get_flag_cells())

    reducer_safe: Set[Coord] = set()
    reducer_flags: Set[Coord] = set()
    if solver.csp_manager and getattr(solver.csp_manager, "reducer_result", None):
        reducer_safe = set(getattr(solver.csp_manager.reducer_result, "safe_cells", []) or [])
        reducer_flags = set(getattr(solver.csp_manager.reducer_result, "flag_cells", []) or [])

    actions: List[SolverAction] = []
    for cell in safe_cells:
        reasoning = "reducer" if cell in reducer_safe else "csp"
        actions.append(
            SolverAction(cell=cell, type=SolverActionType.CLICK, confidence=1.0, reasoning=reasoning)
        )
    for cell in flag_cells:
        reasoning = "reducer" if cell in reducer_flags else "csp"
        actions.append(
            SolverAction(cell=cell, type=SolverActionType.FLAG, confidence=1.0, reasoning=reasoning)
        )

    if not actions and allow_guess:
        guess = solver.get_best_guess()
        if guess:
            x, y, prob = guess
            actions.append(
                SolverAction(
                    cell=(x, y),
                    type=SolverActionType.GUESS,
                    confidence=1.0 - prob,
                    reasoning=f"CSP Best Guess ({prob*100:.1f}% mine)",
                )
            )

    stats = SolverStats(
        zones_analyzed=len(solver.segmentation.zones) if solver.segmentation else 0,
        components_solved=len(solver.segmentation.components) if solver.segmentation else 0,
        safe_cells=len(safe_cells),
        flag_cells=len(flag_cells),
    )
    # Expose actions to csp_manager for overlays
    if solver.csp_manager is not None:
        try:
            solver.csp_manager.actions = actions
        except Exception:
            pass

    updated_cells = build_metadata_updates(cells, frontier_coords, safe_cells, flag_cells, solver.segmentation)
    active_remove = compute_active_remove(updated_cells or cells)
    # Recalculer la frontière après mise à jour des états (flags/safe)
    new_frontier = compute_frontier_from_cells(updated_cells or cells)
    frontier_add = set(new_frontier) - current_frontier_in_bounds
    frontier_remove = current_frontier_in_bounds - set(new_frontier)

    # Déduplication (cell, type) pour éviter les double-exécutions (ex: flags) – uniquement sur actions solver
    dedup_actions: list[SolverAction] = []
    seen: set[tuple[Coord, SolverActionType]] = set()
    for a in actions:
        key = (a.cell, a.type)
        if key in seen:
            continue
        seen.add(key)
        dedup_actions.append(a)

    # Cleanup bonus : après le solver, basé sur TO_REDUCE et ACTIVE voisines
    merged_cells: Dict[Coord, GridCell] = {
        coord: updated_cells.get(coord, cell) for coord, cell in cells.items()
    }
    cleanup_actions: list[SolverAction] = []
    cleanup_targets: set[Coord] = set()
    if enable_cleanup:
        cleanup_actions = build_cleanup_actions(merged_cells)
        cleanup_targets = {a.cell for a in cleanup_actions}

    storage_upsert = StorageUpsert(
        cells=updated_cells,
        active_remove=active_remove,
        frontier_add=frontier_add,
        frontier_remove=frontier_remove,
        to_visualize=safe_cells,
    )

    return SolverUpdate(
        actions=dedup_actions,
        cleanup_actions=cleanup_actions,
        stats=stats,
        storage_upsert=storage_upsert,
        cleanup_targets=cleanup_targets,
    )


def _classify_solver_status(
    coord: Coord,
    cell: GridCell,
    frontier_coords: Set[Coord],
    cells: Dict[Coord, GridCell],
) -> SolverStatus:
    if coord in frontier_coords and cell.logical_state == LogicalCellState.UNREVEALED:
        return SolverStatus.FRONTIER

    if cell.logical_state == LogicalCellState.OPEN_NUMBER:
        if _has_unrevealed_neighbor(coord, cells):
            return SolverStatus.ACTIVE
        return SolverStatus.SOLVED

    if cell.logical_state in {LogicalCellState.EMPTY, LogicalCellState.CONFIRMED_MINE}:
        return SolverStatus.SOLVED

    if cell.logical_state == LogicalCellState.UNREVEALED:
        return SolverStatus.NONE

    return cell.solver_status


def _has_unrevealed_neighbor(coord: Coord, cells: Dict[Coord, GridCell]) -> bool:
    for nx, ny in _iter_neighbors(coord):
        neighbor = cells.get((nx, ny))
        if neighbor and neighbor.logical_state == LogicalCellState.UNREVEALED:
            return True
    return False


def _iter_neighbors(coord: Coord):
    x, y = coord
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield x + dx, y + dy
