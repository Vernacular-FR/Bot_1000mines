#!/usr/bin/env python3
"""Génère un overlay des statuts ACTIVE / FRONTIER / SOLVED à partir des screenshots 00_raw_grids."""

from __future__ import annotations

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections.abc import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CELL_BORDER, CELL_SIZE  # noqa: E402
from src.lib.s2_vision.facade import VisionAPI, VisionControllerConfig  # noqa: E402
from src.lib.s2_vision.s21_template_matcher import MatchResult  # noqa: E402
from src.lib.s3_storage.facade import GridCell, LogicalCellState  # noqa: E402
from src.lib.s2_vision.s23_vision_to_storage import matches_to_upsert  # noqa: E402
from src.lib.s4_solver.facade import SolverAction, SolverActionType  # noqa: E402
from src.lib.s4_solver.s40_grid_analyzer.grid_classifier import FrontierClassifier  # noqa: E402
from src.lib.s4_solver.s40_grid_analyzer.zone_overlay import render_zone_overlay  # noqa: E402
from src.lib.s4_solver.s41_propagator_solver.actions_overlay import (  # noqa: E402
    render_actions_overlay,
)
from src.lib.s4_solver.s41_propagator_solver.s411_frontiere_reducer import (  # noqa: E402
    IterativePropagator,
)
from src.lib.s4_solver.s41_propagator_solver.s412_subset_constraint_propagator import (  # noqa: E402
    SubsetConstraintPropagator,
)
from src.lib.s4_solver.s41_propagator_solver.s413_advanced_constraint_engine import (  # noqa: E402
    AdvancedConstraintEngine,
)
from src.lib.s4_solver.s41_propagator_solver.combined_overlay import render_combined_overlay  # noqa: E402


Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

STRIDE = CELL_SIZE + CELL_BORDER
RAW_GRIDS_DIR = Path(__file__).parent / "00_raw_grids"
VISION_OVERLAYS_DIR = Path(__file__).parent / "s3_vision_overlays"
ZONE_OVERLAYS_DIR = Path(__file__).parent / "s40_zones_overlays"
PATTERN_OVERLAYS_DIR = Path(__file__).parent / "s41_propagator_solver_overlay"
COMBINED_OVERLAYS_DIR = Path(__file__).parent / "s42_final_combined_overlay"
BOUNDS_PATTERN = re.compile(r"zone_(?P<sx>-?\d+)_(?P<sy>-?\d+)_(?P<ex>-?\d+)_(?P<ey>-?\d+)")

ACTIVE_COLOR = (0, 120, 255, 180)
FRONTIER_COLOR = (255, 170, 0, 200)
SOLVED_COLOR = (0, 180, 90, 180)


def parse_bounds(path: Path) -> Optional[Bounds]:
    match = BOUNDS_PATTERN.search(path.stem)
    if not match:
        return None
    return (
        int(match.group("sx")),
        int(match.group("sy")),
        int(match.group("ex")),
        int(match.group("ey")),
    )


def analyze_screenshot(screenshot: Path) -> Tuple[Bounds, Dict[Tuple[int, int], MatchResult]]:
    bounds = parse_bounds(screenshot)
    if not bounds:
        raise ValueError(f"Impossible de parser les bornes pour {screenshot.name}")

    start_x, start_y, end_x, end_y = bounds
    grid_width = end_x - start_x + 1
    grid_height = end_y - start_y + 1

    VISION_OVERLAYS_DIR.mkdir(exist_ok=True, parents=True)
    vision = VisionAPI(VisionControllerConfig(overlay_output_dir=VISION_OVERLAYS_DIR))
    matches = vision.analyze_screenshot(
        screenshot_path=str(screenshot),
        grid_top_left=(0, 0),
        grid_size=(grid_width, grid_height),
        stride=STRIDE,
        overlay=True,
    )
    generated_overlay = VISION_OVERLAYS_DIR / f"{screenshot.stem}_overlay.png"
    if generated_overlay.exists():
        target_overlay = VISION_OVERLAYS_DIR / f"{screenshot.stem}_vision_overlay.png"
        if target_overlay.exists():
            target_overlay.unlink()
        generated_overlay.rename(target_overlay)
    return bounds, matches


def _neighbors(coord: Coord) -> Iterable[Coord]:
    x, y = coord
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield x + dx, y + dy


def infer_pattern_moves(
    cells: Dict[Coord, GridCell], frontier: set[Coord]
) -> Tuple[set[Coord], set[Coord]]:
    """
    Règle simple :
    - si une case active possède déjà autant de mines confirmées que sa valeur,
      toutes ses voisines fermées restantes sont sûres.
    - si la somme (mines confirmées + voisines fermées) == valeur,
      alors toutes ces voisines fermées sont des mines (flags certains).
    - seules les voisines présentes dans la frontière sont retournées.
    """
    safe: set[Coord] = set()
    flags: set[Coord] = set()
    for coord, cell in cells.items():
        if cell.logical_state != LogicalCellState.OPEN_NUMBER or cell.number_value is None:
            continue
        flagged = 0
        candidates: list[Coord] = []
        for nb in _neighbors(coord):
            neighbor = cells.get(nb)
            if not neighbor:
                continue
            if neighbor.logical_state == LogicalCellState.CONFIRMED_MINE:
                flagged += 1
            elif neighbor.logical_state == LogicalCellState.UNREVEALED:
                candidates.append(nb)
        if not candidates:
            continue
        # Toutes les mines déjà trouvées -> le reste est safe
        if flagged >= cell.number_value:
            for nb in candidates:
                if nb in frontier:
                    safe.add(nb)
        # Sinon, si on doit placer autant de mines que de fermées restantes
        elif flagged + len(candidates) == cell.number_value:
            for nb in candidates:
                if nb in frontier:
                    flags.add(nb)
    return safe, flags


def process_screenshot(screenshot: Path) -> None:
    bounds, matches = analyze_screenshot(screenshot)
    upsert = matches_to_upsert(bounds, matches)
    cells = upsert.cells
    
    # Phase 1 : propagation itérative (règles locales)
    frontiere_reducer = IterativePropagator(cells)
    iterative_result = frontiere_reducer.solve_with_zones()
    
    # Phase 1.5 : propagation par inclusion de contraintes
    subset_propagator = SubsetConstraintPropagator(cells)
    subset_propagator.apply_known_actions(
        safe_cells=iterative_result.safe_cells,
        flag_cells=iterative_result.flag_cells,
    )
    subset_result = subset_propagator.solve_with_zones()
    
    # Phase 2.5 : propagation avancée (unions partielles / pairwise elimination)
    advanced_engine = AdvancedConstraintEngine(cells)
    advanced_engine.apply_known_actions(
        safe_cells=iterative_result.safe_cells.union(subset_result.safe_cells),
        flag_cells=iterative_result.flag_cells.union(subset_result.flag_cells),
    )
    advanced_result = advanced_engine.solve_with_zones()
    
    # Extraire les zones depuis le résultat pour l'overlay des zones
    from src.lib.s4_solver.s40_grid_analyzer.grid_classifier import FrontierClassifier
    classifier = FrontierClassifier(cells)
    zones = classifier.classify()
    
    overlay_path = render_zone_overlay(
        screenshot,
        bounds,
        active=zones.active,
        frontier=zones.frontier,
        solved=zones.solved,
        stride=STRIDE,
        cell_size=CELL_SIZE,
        output_dir=ZONE_OVERLAYS_DIR,
    )
    
    # Créer les actions à partir du résultat de la propagation
    actions: List[SolverAction] = []
    def _build_actions(coords: Iterable[Coord], action_type: SolverActionType, reasoning: str) -> List[SolverAction]:
        return [
            SolverAction(
                cell=coord,
                type=action_type,
                confidence=1.0,
                reasoning=reasoning,
            )
            for coord in sorted(coords)
        ]

    # Actions issues de la phase itérative
    if iterative_result.safe_cells:
        actions.extend(
            _build_actions(
                iterative_result.safe_cells,
                SolverActionType.CLICK,
                f"iterative-propagation-{iterative_result.iterations}iters",
            )
        )
    if iterative_result.flag_cells:
        actions.extend(
            _build_actions(
                iterative_result.flag_cells,
                SolverActionType.FLAG,
                f"iterative-propagation-{iterative_result.iterations}iters",
            )
        )

    # Actions supplémentaires déduites par la phase subset (hors doublons)
    subset_new_safe = subset_result.safe_cells - iterative_result.safe_cells
    subset_new_flags = subset_result.flag_cells - iterative_result.flag_cells
    
    # Actions supplémentaires déduites par la phase avancée (hors doublons)
    advanced_baseline_safe = iterative_result.safe_cells.union(subset_result.safe_cells)
    advanced_baseline_flags = iterative_result.flag_cells.union(subset_result.flag_cells)
    advanced_new_safe = advanced_result.safe_cells - advanced_baseline_safe
    advanced_new_flags = advanced_result.flag_cells - advanced_baseline_flags
    if subset_new_safe:
        actions.extend(
            _build_actions(
                subset_new_safe,
                SolverActionType.CLICK,
                f"subset-propagation-{subset_result.iterations}iters",
            )
        )
    if subset_new_flags:
        actions.extend(
            _build_actions(
                subset_new_flags,
                SolverActionType.FLAG,
                f"subset-propagation-{subset_result.iterations}iters",
            )
        )
        print(f"    ↳ Subset flags: {sorted(subset_new_flags)}")
    if subset_new_safe:
        print(f"    ↳ Subset safe: {sorted(subset_new_safe)}")
    
    if advanced_new_safe:
        actions.extend(
            _build_actions(
                advanced_new_safe,
                SolverActionType.CLICK,
                f"advanced-propagation-{advanced_result.iterations}iters",
            )
        )
        print(f"    ↳ Advanced safe: {sorted(advanced_new_safe)}")
    if advanced_new_flags:
        actions.extend(
            _build_actions(
                advanced_new_flags,
                SolverActionType.FLAG,
                f"advanced-propagation-{advanced_result.iterations}iters",
            )
        )
        print(f"    ↳ Advanced flags: {sorted(advanced_new_flags)}")

    combined_safe = iterative_result.safe_cells | subset_result.safe_cells | advanced_result.safe_cells
    combined_flags = iterative_result.flag_cells | subset_result.flag_cells | advanced_result.flag_cells

    if actions:
        output_dir = PATTERN_OVERLAYS_DIR
        output_dir.mkdir(exist_ok=True, parents=True)
        render_actions_overlay(
            screenshot,
            bounds,
            actions=actions,
            stride=STRIDE,
            cell_size=CELL_SIZE,
            output_dir=output_dir,
        )
        safe_count = len(combined_safe)
        flag_count = len(combined_flags)
        print(
            f"[PATTERN] {screenshot.name}: "
            f"iter_safe={len(iterative_result.safe_cells)} iter_flags={len(iterative_result.flag_cells)} "
            f"subset_safe={len(subset_new_safe)} subset_flags={len(subset_new_flags)} "
            f"adv_safe={len(advanced_new_safe)} adv_flags={len(advanced_new_flags)} "
            f"(overlay: {output_dir.name})"
        )
        print(f"  Iterative reasoning: {iterative_result.reasoning}")
        print(f"  Subset reasoning: {subset_result.reasoning}")
        print(f"  Advanced reasoning: {advanced_result.reasoning}")
        
        # Générer l'overlay combiné (zones + actions)
        combined_path = render_combined_overlay(
            screenshot,
            bounds,
            actions=actions,
            zones=(zones.active, zones.frontier, zones.solved),
            cells=cells,  # ✅ Ajouter les cellules pour calculer effective values
            stride=STRIDE,
            cell_size=CELL_SIZE,
            output_dir=COMBINED_OVERLAYS_DIR,
        )
        print(f"[COMBINED] {screenshot.name}: zones + solver → {combined_path.name}")

    print(
        f"[ZONES] {screenshot.name}: "
        f"active={len(zones.active)}, frontier={len(zones.frontier)}, solved={len(zones.solved)} "
        f"→ {overlay_path.name}"
    )


def main() -> None:
    screenshots: List[Path] = sorted(RAW_GRIDS_DIR.glob("*.png"))
    if not screenshots:
        print(f"[ERROR] Aucun screenshot trouvé dans {RAW_GRIDS_DIR}")
        return

    print("=" * 50)
    print("GENERATION OVERLAYS ZONES (ACTIVE / FRONTIER / SOLVED)")
    print("=" * 50)

    for screenshot in screenshots:
        try:
            process_screenshot(screenshot)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[ERROR] {screenshot.name}: {exc}")


if __name__ == "__main__":
    main()
