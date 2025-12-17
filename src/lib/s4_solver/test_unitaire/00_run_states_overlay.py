#!/usr/bin/env python3
"""Génère un overlay des statuts ACTIVE / FRONTIER / SOLVED à partir des screenshots 00_raw_grids."""

from __future__ import annotations

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CELL_BORDER, CELL_SIZE  # noqa: E402
from src.lib.s2_vision.facade import VisionAPI, VisionControllerConfig  # noqa: E402
from src.lib.s2_vision.s21_template_matcher import MatchResult  # noqa: E402
from src.lib.s3_storage.facade import GridCell  # noqa: E402
from src.lib.s2_vision.s23_vision_to_storage import matches_to_upsert  # noqa: E402
from src.lib.s4_solver.s40_states_classifier.grid_classifier import FrontierClassifier  # noqa: E402
from src.lib.s4_solver.s49_overlays.s491_states_overlay import render_states_overlay  # noqa: E402
from src.lib.s1_capture.s10_overlay_utils import setup_overlay_context  # noqa: E402


Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

EXPORT_ROOT = Path(__file__).parent / "00_states"
STRIDE = CELL_SIZE + CELL_BORDER
RAW_GRIDS_DIR = Path(__file__).parent / "00_raw_grids"
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

    EXPORT_ROOT.mkdir(exist_ok=True, parents=True)
    vision = VisionAPI(VisionControllerConfig(overlay_output_dir=EXPORT_ROOT))
    matches = vision.analyze_screenshot(
        screenshot_path=str(screenshot),
        grid_top_left=(0, 0),
        grid_size=(grid_width, grid_height),
        stride=STRIDE,
        overlay=True,
    )
    return bounds, matches


def process_screenshot(screenshot: Path) -> None:
    bounds, matches = analyze_screenshot(screenshot)
    # Publier le contexte overlay pour les renderers
    setup_overlay_context(
        export_root=EXPORT_ROOT,
        screenshot=screenshot,
        bounds=bounds,
        stride=STRIDE,
        game_id=screenshot.stem,
        iteration=0,
        cell_size=CELL_SIZE,
    )
    upsert = matches_to_upsert(bounds, matches)
    cells = upsert.cells
    overlay_path = render_states_overlay(
        screenshot,
        bounds,
        cells=cells,
        stride=STRIDE,
        cell_size=CELL_SIZE,
        export_root=EXPORT_ROOT,
    )
    print(f"[ZONES] {screenshot.name}: overlay → {overlay_path.name}")


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
