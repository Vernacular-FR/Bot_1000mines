from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.config import CELL_BORDER, CELL_SIZE
from src.lib.s2_vision.s21_template_matcher import MatchResult
from src.lib.s3_storage.facade import CellState, GridCell, StorageUpsert
from src.lib.s4_solver.facade import SolverAction, SolverActionType

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

STRIDE = CELL_SIZE + CELL_BORDER

ACTIONS_COLORS = {
    SolverActionType.CLICK: (0, 200, 0, 160),
    SolverActionType.FLAG: (255, 0, 0, 160),
    SolverActionType.GUESS: (255, 165, 0, 160),
}


def _neighbors(coord: Coord) -> Iterable[Coord]:
    x, y = coord
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield x + dx, y + dy


def _symbol_to_state(symbol: str) -> Tuple[CellState, Optional[int]]:
    if symbol.startswith("number_"):
        try:
            value = int(symbol.split("_", maxsplit=1)[1])
        except ValueError:
            value = None
        return CellState.OPEN_NUMBER, value
    if symbol == "empty":
        return CellState.OPEN_EMPTY, 0
    if symbol == "flag":
        return CellState.FLAG, None
    if symbol == "exploded":
        return CellState.FLAG, None  # Exploded mines count as confirmed mines
    return CellState.CLOSED, None


def matches_to_upsert(
    bounds: Bounds,
    matches: Dict[Tuple[int, int], MatchResult],
) -> StorageUpsert:
    start_x, start_y, _, _ = bounds

    cells: Dict[Coord, GridCell] = {}
    revealed: set[Coord] = set()
    closed: set[Coord] = set()
    
    for (row, col), match in matches.items():
        x = start_x + col
        y = start_y + row
        state, value = _symbol_to_state(match.symbol)
        cell = GridCell(x=x, y=y, state=state, value=value)
        cells[(x, y)] = cell
        if state in (CellState.OPEN_NUMBER, CellState.OPEN_EMPTY):
            revealed.add((x, y))
        elif state == CellState.CLOSED:  # Only CLOSED cells, not FLAG or UNKNOWN
            closed.add((x, y))
        # FLAG cells are NOT added to either revealed or closed - they're confirmed mines

    frontier: set[Coord] = set()
    for coord in revealed:
        for nb in _neighbors(coord):
            if nb in closed:
                frontier.add(nb)

    return StorageUpsert(
        cells=cells,
        revealed_add=revealed,
        unresolved_add=revealed.copy(),
        frontier_add=frontier,
    )


def render_solver_overlay(
    base_image_path: Path,
    bounds: Bounds,
    actions: List[SolverAction],
    output_dir: Path,
) -> Optional[Path]:
    if not actions:
        return None

    image = Image.open(base_image_path).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    start_x, start_y, _, _ = bounds

    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()

    for action in actions:
        cell_x, cell_y = action.cell
        col = cell_x - start_x
        row = cell_y - start_y
        if col < 0 or row < 0:
            continue
        x0 = col * STRIDE
        y0 = row * STRIDE
        x1 = x0 + CELL_SIZE
        y1 = y0 + CELL_SIZE
        color = ACTIONS_COLORS.get(action.type, (0, 0, 255, 160))

        draw.rectangle([(x0, y0), (x1, y1)], outline=(255, 255, 255, 255), width=1)
        draw.rectangle([(x0 + 1, y0 + 1), (x1 - 1, y1 - 1)], fill=color)

        label = {
            SolverActionType.CLICK: "C",
            SolverActionType.FLAG: "F",
            SolverActionType.GUESS: "G",
        }.get(action.type, "?")
        draw.text((x0 + 3, y0 + 3), label, font=font, fill=(255, 255, 255, 255))

    composed = Image.alpha_composite(image, overlay)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{Path(base_image_path).stem}_solver_overlay.png"
    composed.save(out_path)
    return out_path
