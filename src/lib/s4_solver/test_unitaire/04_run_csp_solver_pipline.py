#!/usr/bin/env python3
"""Génère un overlay des statuts ACTIVE / FRONTIER / SOLVED à partir des screenshots 00_raw_grids."""

from __future__ import annotations

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections.abc import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CELL_BORDER, CELL_SIZE  # noqa: E402
from src.lib.s4_solver.facade import SolverAction, SolverActionType  # noqa: E402
from src.services.s3_game_solver_service import GameSolverServiceV2  # noqa: E402


Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

STRIDE = CELL_SIZE + CELL_BORDER
RAW_GRIDS_DIR = Path(__file__).parent / "00_raw_grids"
EXPORT_ROOT = Path(__file__).parent / "04_csp_pipline"
BOUNDS_PATTERN = re.compile(r"zone_(?P<sx>-?\d+)_(?P<sy>-?\d+)_(?P<ex>-?\d+)_(?P<ey>-?\d+)")

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


def process_screenshot(screenshot: Path) -> None:
    solver_service = GameSolverServiceV2()
    solve_result = solver_service.solve_from_screenshot_file(
        screenshot,
        solver_overlay_dir=EXPORT_ROOT,
        emit_solver_overlays=True,
    )
    bounds = solve_result.get("bounds")
    stride = solve_result.get("stride", STRIDE)
    actions = solve_result.get("actions", [])
    stats = solve_result.get("stats")
    states_overlay = solve_result.get("states)

    pipeline_safe: Set[Coord] = set(solve_result.get("reducer_safe") or [])
    pipeline_flags: Set[Coord] = set(solve_result.get("reducer_flags") or [])
    csp_safe: Set[Coord] = {a.cell for a in actions if a.type == SolverActionType.CLICK}
    csp_flags: Set[Coord] = {a.cell for a in actions if a.type == SolverActionType.FLAG}

    print(f"[STATS] zones_analyzed={getattr(stats, 'zones_analyzed', None)} components_solved={getattr(stats, 'components_solved', None)}")
    print(
        f"[CSP] {screenshot.name}: "
        f"reducer_safe={len(pipeline_safe)} reducer_flags={len(pipeline_flags)} "
        f"csp_safe={len(csp_safe)} csp_flags={len(csp_flags)} "
        f"(overlay: {EXPORT_ROOT.name})"
    )
    if states_overlay:
        print(f"[STATES] {Path(states_overlay).name}")


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
