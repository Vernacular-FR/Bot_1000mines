from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.lib.s4_solver.facade import SolverAction, SolverActionType

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

# Couleurs de base (servira pour CSP opaque)
ACTIONS_COLORS = {
    SolverActionType.CLICK: (0, 255, 0),           # Vert vif pour safe
    SolverActionType.FLAG: (255, 0, 0),            # Rouge vif pour flag
    SolverActionType.GUESS: (250, 220, 0),         # Jaune foncé pour guess
}


def draw_action_on_image(
    draw: ImageDraw.ImageDraw,
    action: SolverAction,
    px: int,
    py: int,
    cell_size: int,
    opacity: int = 255,
) -> None:
    """
    Dessine une seule action sur une image.
    """
    color = ACTIONS_COLORS.get(action.type, (128, 128, 128))
    color = (*color[:3], opacity)
    
    # Dessiner l'action (carré très visible, sans bordure)
    margin = 2
    draw.rectangle(
        [px + margin, py + margin, px + cell_size - margin, py + cell_size - margin],
        fill=color,
        outline=None,  # Pas de bordure noire
    )
    
    # Ajouter une croix au centre pour encore plus de visibilité
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
    elif action.type == SolverActionType.GUESS:
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


def render_actions_overlay(
    screenshot: Path,
    bounds: Bounds,
    reducer_actions: Iterable[SolverAction],
    csp_actions: Iterable[SolverAction],
    stride: int,
    cell_size: int,
    export_root: Path,
) -> Path:
    """
    Dessine deux couches :
    - actions du FrontiereReducer en transparent
    - actions CSP en opaque
    """
    image = Image.open(screenshot).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, _, _ = bounds

    for action in reducer_actions:
        if not action.cell or len(action.cell) != 2:
            continue
        cell_x, cell_y = action.cell
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw, action, px, py, cell_size, opacity=60)

    for action in csp_actions:
        if not action.cell or len(action.cell) != 2:
            continue
        cell_x, cell_y = action.cell
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw, action, px, py, cell_size, opacity=255)

    composed = Image.alpha_composite(image, overlay)
    out_dir = Path(export_root) / "s42_solver_overlay"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{screenshot.stem}_solver_overlay.png"
    composed.save(out_path)
    return out_path
