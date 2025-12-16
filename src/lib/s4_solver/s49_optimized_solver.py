from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Set, Tuple, Optional

from src.lib.s3_storage.s30_session_context import get_session_context
from src.config import CELL_SIZE, CELL_BORDER

from src.lib.s3_storage.facade import (
    ActionStatus,
    Bounds,
    Coord,
    GridCell,
    LogicalCellState,
    SolverStatus,
    StorageUpsert,
)
from src.lib.s4_solver.facade import SolverAction, SolverActionType, SolverStats
from src.lib.s4_solver.s40_states_analyzer.grid_extractor import SolverFrontierView
from src.lib.s4_solver.s42_csp_solver.s420_csp_manager import CspManager
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
        self.overlay_metadata = overlay_metadata or self._build_overlay_metadata_from_session()

    def solve(self) -> None:
        self.zone_probabilities.clear()
        self.solutions_by_component.clear()
        self.safe_cells.clear()
        self.flag_cells.clear()
        self.segmentation = None
        self.csp_manager = None

        if not self.overlay_metadata:
            self.overlay_metadata = self._build_overlay_metadata_from_session()

        # Exécuter le pipeline CSP complet (réducteur + segmentation + CSP)
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
        self.csp_manager.run_with_frontier_reducer()
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

    # ------------------------------------------------------------------
    # Overlay metadata
    # ------------------------------------------------------------------
    def _build_overlay_metadata_from_session(self) -> Dict:
        ctx = get_session_context()
        if not (ctx.overlay_enabled and ctx.export_root and ctx.capture_saved_path):
            return {}
        bounds = ctx.capture_bounds or compute_bounds(set(self.cells.keys()))
        stride = ctx.capture_stride or (CELL_SIZE + CELL_BORDER)
        cell_size = CELL_SIZE
        if not (bounds and stride and cell_size):
            return {}
        return {
            "export_root": ctx.export_root,
            "screenshot_path": ctx.capture_saved_path,
            "bounds": bounds,
            "stride": stride,
            "cell_size": cell_size,
        }

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
    stats: SolverStats
    storage_upsert: StorageUpsert


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
) -> Dict[Coord, GridCell]:
    safe_set = set(safe_cells)
    flag_set = set(flag_cells)
    updated: Dict[Coord, GridCell] = {}

    for coord, cell in cells.items():
        desired_status = _classify_solver_status(coord, cell, frontier_coords, cells)
        desired_action = cell.action_status

        if coord in safe_set:
            desired_status = SolverStatus.SOLVED
            desired_action = ActionStatus.SAFE
        elif coord in flag_set:
            desired_status = SolverStatus.SOLVED
            desired_action = ActionStatus.FLAG
        elif desired_action != ActionStatus.NONE:
            desired_action = ActionStatus.NONE

        if desired_status != cell.solver_status or desired_action != cell.action_status:
            updated[coord] = replace(
                cell,
                solver_status=desired_status,
                action_status=desired_action,
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


def compute_unresolved_remove(
    cells: Dict[Coord, GridCell],
) -> Set[Coord]:
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
) -> SolverUpdate:
    safe_cells = set(solver.get_safe_cells())
    flag_cells = set(solver.get_flag_cells())

    actions: List[SolverAction] = []
    actions.extend(
        SolverAction(cell=cell, type=SolverActionType.CLICK, confidence=1.0, reasoning="csp")
        for cell in safe_cells
    )
    actions.extend(
        SolverAction(cell=cell, type=SolverActionType.FLAG, confidence=1.0, reasoning="csp")
        for cell in flag_cells
    )

    if not actions:
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

    updated_cells = build_metadata_updates(cells, frontier_coords, safe_cells, flag_cells)
    unresolved_remove = compute_unresolved_remove(cells)
    frontier_add = set(frontier_coords) - current_frontier_in_bounds
    frontier_remove = current_frontier_in_bounds - set(frontier_coords)

    storage_upsert = StorageUpsert(
        cells=updated_cells,
        unresolved_remove=unresolved_remove,
        frontier_add=frontier_add,
        frontier_remove=frontier_remove,
    )

    return SolverUpdate(actions=actions, stats=stats, storage_upsert=storage_upsert)


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
