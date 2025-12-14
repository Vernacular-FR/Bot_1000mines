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
from src.lib.s4_solver.s40_grid_analyzer.grid_extractor import SolverFrontierView  # noqa: E402
from src.lib.s4_solver.s40_grid_analyzer.zone_overlay import render_zone_overlay  # noqa: E402
from src.lib.s4_solver.s41_propagator_solver.combined_overlay import render_combined_overlay  # noqa: E402
from src.lib.s4_solver.s41_propagator_solver.s410_propagator_pipeline import (  # noqa: E402
    PropagatorPipeline,
    PropagatorPipelineResult,
)
from src.lib.s4_solver.s41_propagator_solver.s411_frontiere_reducer import (  # noqa: E402
    PropagationResult,
)
from src.lib.s4_solver.s42_csp_solver.s420_csp_manager import CspManager  # noqa: E402
from src.lib.s4_solver.s42_csp_solver.actions_overlay import (  # noqa: E402
    render_actions_overlay,
)
from src.lib.s4_solver.s42_csp_solver.segmentation_overlay import (  # noqa: E402
    render_segmentation_overlay,
)


Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

STRIDE = CELL_SIZE + CELL_BORDER
RAW_GRIDS_DIR = Path(__file__).parent / "00_raw_grids"
VISION_OVERLAYS_DIR = Path(__file__).parent / "s3_vision_overlays"
ZONE_OVERLAYS_DIR = Path(__file__).parent / "s40_zones_overlays"
CSP_OVERLAYS_DIR = Path(__file__).parent / "s42_csp_solver_overlay"
SEGMENTATION_OVERLAYS_DIR = Path(__file__).parent / "s42_segmentation_overlay"
COMBINED_OVERLAYS_DIR = Path(__file__).parent / "s43_csp_combined_overlay"
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


def process_screenshot(screenshot: Path) -> None:
    bounds, matches = analyze_screenshot(screenshot)
    upsert = matches_to_upsert(bounds, matches)
    cells = upsert.cells
    
    # Classification pour overlay + vue CSP
    from src.lib.s4_solver.s40_grid_analyzer.grid_classifier import FrontierClassifier
    classifier = FrontierClassifier(cells)
    zones = classifier.classify()
    frontier_coords = set(zones.frontier)
    view = SolverFrontierView(cells, frontier_coords)
    
    # Étape CSP autonome (avec frontiere reducer minimal)
    csp_manager = CspManager(view, cells)
    csp_manager.run_with_frontier_reducer()
    reducer_result = csp_manager.reducer_result
    pipeline_safe: Set[Coord] = reducer_result.safe_cells if reducer_result else set()
    pipeline_flags: Set[Coord] = reducer_result.flag_cells if reducer_result else set()
    csp_safe = set(csp_manager.safe_cells)
    csp_flags = set(csp_manager.flag_cells)
    segmentation_overlay_path: Path | None = None
    if csp_manager.segmentation:
        segmentation_overlay_path = render_segmentation_overlay(
            screenshot,
            bounds,
            segmentation=csp_manager.segmentation,
            stride=STRIDE,
            cell_size=CELL_SIZE,
            output_dir=SEGMENTATION_OVERLAYS_DIR,
        )
    
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
    
    # Créer les actions (reducer + CSP) pour l'overlay
    actions: List[SolverAction] = []
    reducer_actions: List[SolverAction] = []
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

    if pipeline_safe:
        reducer_actions.extend(
            _build_actions(
                pipeline_safe,
                SolverActionType.CLICK,
                "frontiere-reducer",
            )
        )
    if pipeline_flags:
        reducer_actions.extend(
            _build_actions(
                pipeline_flags,
                SolverActionType.FLAG,
                "frontiere-reducer",
            )
        )

    if csp_safe:
        actions.extend(
            _build_actions(
                csp_safe,
                SolverActionType.CLICK,
                "csp-solver",
            )
        )
        print(f"    ↳ CSP safe: {sorted(csp_safe)}")
    if csp_flags:
        actions.extend(
            _build_actions(
                csp_flags,
                SolverActionType.FLAG,
                "csp-solver",
            )
        )
        print(f"    ↳ CSP flags: {sorted(csp_flags)}")

    combined_safe = pipeline_safe.union(csp_safe)
    combined_flags = pipeline_flags.union(csp_flags)

    output_dir = CSP_OVERLAYS_DIR
    output_dir.mkdir(exist_ok=True, parents=True)
    render_actions_overlay(
        screenshot,
        bounds,
        reducer_actions=reducer_actions,
        csp_actions=actions,
        stride=STRIDE,
        cell_size=CELL_SIZE,
        output_dir=output_dir,
    )
    safe_count = len(combined_safe)
    flag_count = len(combined_flags)
    print(
        f"[CSP] {screenshot.name}: "
        f"reducer_safe={len(pipeline_safe)} reducer_flags={len(pipeline_flags)} "
        f"csp_safe={len(csp_safe)} csp_flags={len(csp_flags)} "
        f"(overlay: {output_dir.name})"
    )
    print(
        f"  CSP zones: {len(csp_manager.segmentation.zones) if csp_manager.segmentation else 0} | "
        f"eligible components={len(csp_manager.solutions_by_component)}"
    )
    if segmentation_overlay_path:
        print(f"[SEGMENTATION] {screenshot.name}: {segmentation_overlay_path.name}")
    
    # Générer l'overlay combiné (zones + actions) même si le CSP n'a rien produit
    combined_path = render_combined_overlay(
        screenshot,
        bounds,
        actions=reducer_actions + actions,
        zones=(zones.active, zones.frontier, zones.solved),
        cells=cells,  # Ajouter les cellules pour calculer effective values
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
