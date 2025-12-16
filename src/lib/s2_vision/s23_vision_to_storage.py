from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.config import CELL_BORDER, CELL_SIZE
from src.lib.s2_vision.s21_template_matcher import MatchResult
from src.lib.s3_storage.facade import (
    GridCell,
    StorageUpsert,
    RawCellState,
    LogicalCellState,
    SolverStatus,
)
from src.lib.s4_solver.facade import SolverAction, SolverActionType
from src.lib.s4_solver.s49_overlays.s493_actions_overlay import render_actions_overlay

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

STRIDE = CELL_SIZE + CELL_BORDER

ACTIONS_COLORS = {
    SolverActionType.CLICK: (0, 200, 0, 160),
    SolverActionType.FLAG: (255, 0, 0, 160),
    SolverActionType.GUESS: (255, 165, 0, 160),
}


def _symbol_to_states(symbol: str) -> Tuple[RawCellState, LogicalCellState, Optional[int]]:
    if symbol.startswith("number_"):
        try:
            value = int(symbol.split("_", maxsplit=1)[1])
        except ValueError:
            value = None
        if value in range(1, 9):
            return RawCellState[f"NUMBER_{value}"], LogicalCellState.OPEN_NUMBER, value
        return RawCellState.UNREVEALED, LogicalCellState.UNREVEALED, None
    if symbol == "empty":
        return RawCellState.EMPTY, LogicalCellState.EMPTY, None
    if symbol == "flag":
        return RawCellState.FLAG, LogicalCellState.CONFIRMED_MINE, None
    if symbol == "exploded":
        return RawCellState.EXPLODED, LogicalCellState.CONFIRMED_MINE, None
    if symbol == "question":
        return RawCellState.QUESTION, LogicalCellState.UNREVEALED, None
    if symbol == "decor":
        return RawCellState.DECOR, LogicalCellState.EMPTY, None
    return RawCellState.UNREVEALED, LogicalCellState.UNREVEALED, None


def matches_to_upsert(
    bounds: Bounds,
    matches: Dict[Tuple[int, int], MatchResult],
) -> StorageUpsert:
    start_x, start_y, _, _ = bounds

    cells: Dict[Coord, GridCell] = {}
    revealed: set[Coord] = set()
    frontier: set[Coord] = set()

    for (row, col), match in matches.items():
        x = start_x + col
        y = start_y + row
        raw_state, logical_state, number_value = _symbol_to_states(match.symbol)

        if logical_state == LogicalCellState.OPEN_NUMBER:
            solver_status = SolverStatus.JUST_REVEALED
        elif logical_state == LogicalCellState.EMPTY:
            solver_status = SolverStatus.JUST_REVEALED
        elif logical_state == LogicalCellState.CONFIRMED_MINE:
            solver_status = SolverStatus.SOLVED
        else:
            solver_status = SolverStatus.NONE

        cell = GridCell(
            x=x,
            y=y,
            raw_state=raw_state,
            logical_state=logical_state,
            number_value=number_value,
            solver_status=solver_status,
        )
        cells[(x, y)] = cell
        if logical_state in (LogicalCellState.OPEN_NUMBER, LogicalCellState.EMPTY):
            revealed.add((x, y))

    # Calcul rapide de la frontière : cases UNREVEALED adjacentes à des révélées
    for (x, y), cell in cells.items():
        if cell.logical_state not in (LogicalCellState.OPEN_NUMBER, LogicalCellState.EMPTY):
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nb = (x + dx, y + dy)
                nb_cell = cells.get(nb)
                if nb_cell and nb_cell.logical_state == LogicalCellState.UNREVEALED:
                    frontier.add(nb)

    return StorageUpsert(
        cells=cells,
        revealed_add=revealed,
        # Unresolved = cellules révélées (nombres/vides) pour le solver
        unresolved_add=revealed.copy(),
        unresolved_remove=set(),
        frontier_add=frontier,
        frontier_remove=set(),
    )


def render_solver_overlay(
    base_image_path: Path,
    bounds: Bounds,
    actions: List[SolverAction],
    export_root: Path,
) -> Optional[Path]:
    if not actions:
        return None
        
    return render_actions_overlay(
        base_image_path,
        bounds,
        reducer_actions=[],
        csp_actions=actions,
        stride=STRIDE,
        cell_size=CELL_SIZE,
        export_root=export_root,
    )
