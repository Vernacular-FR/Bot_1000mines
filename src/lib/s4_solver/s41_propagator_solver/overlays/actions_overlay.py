from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.lib.s4_solver.facade import SolverAction, SolverActionType

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

# Couleurs améliorées pour les actions
ACTIONS_COLORS = {
    SolverActionType.CLICK: (0, 255, 0),
    SolverActionType.FLAG: (255, 0, 0),
    SolverActionType.GUESS: (255, 255, 0),
}


def draw_action_on_image(
    draw: ImageDraw.ImageDraw,
    action: SolverAction,
    px: int,
    py: int,
    cell_size: int,
    opacity: int = 255,
) -> None:
    """Dessine une action avec une opacité configurable."""
    color = ACTIONS_COLORS.get(action.type, (128, 128, 128))
    color = (*color[:3], opacity)
    
    margin = 2
    draw.rectangle(
        [px + margin, py + margin, px + cell_size - margin, py + cell_size - margin],
        fill=color,
        outline=None,
    )
    
    center_x = px + cell_size // 2
    center_y = py + cell_size // 2
    cross_size = 8
    
    if action.type == SolverActionType.CLICK:
        draw.line(
            [center_x - cross_size, center_y, center_x + cross_size, center_y],
            fill=(255, 255, 255, opacity),
            width=3,
        )
        draw.line(
            [center_x, center_y - cross_size, center_x, center_y + cross_size],
            fill=(255, 255, 255, opacity),
            width=3,
        )
    elif action.type == SolverActionType.FLAG:
        draw.ellipse(
            [
                center_x - cross_size // 2,
                center_y - cross_size // 2,
                center_x + cross_size // 2,
                center_y + cross_size // 2,
            ],
            fill=(255, 255, 255, opacity),
        )


def render_actions_overlay(
    screenshot: Path,
    bounds: Bounds,
    actions: Iterable[SolverAction] | None = None,
    phase1_actions: Iterable[SolverAction] | None = None,
    later_actions: Iterable[SolverAction] | None = None,
    stride: int = 0,
    cell_size: int = 0,
    output_dir: Path | None = None,
) -> Path:
    """
    Dessine les actions proposées par le solver.
    - Phase 1 (iterative) dessinée en transparence
    - Phases suivantes en opaque
    Paramètre `actions` conservé pour compatibilité (dessine tout en opaque).
    """
    if output_dir is None:
        raise ValueError("output_dir is required")

    if phase1_actions is None and later_actions is None:
        phase1_list: list[SolverAction] = []
        later_list: list[SolverAction] = list(actions or [])
    else:
        phase1_list = list(phase1_actions or [])
        later_list = list(later_actions or [])

    image = Image.open(screenshot).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, _, _ = bounds

    for action in phase1_list:
        if not action.cell or len(action.cell) != 2:
            continue
        cell_x, cell_y = action.cell
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw, action, px, py, cell_size, opacity=60)

    for action in later_list:
        if not action.cell or len(action.cell) != 2:
            continue
        cell_x, cell_y = action.cell
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw, action, px, py, cell_size, opacity=255)

    composed = Image.alpha_composite(image, overlay)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{screenshot.stem}_solver_overlay.png"
    composed.save(out_path)
    return out_path
