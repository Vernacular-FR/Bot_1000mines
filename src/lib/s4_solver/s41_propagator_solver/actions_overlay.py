from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image, ImageDraw, ImageFont

from src.lib.s4_solver.facade import SolverAction, SolverActionType

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

# Couleurs améliorées pour les actions (opaques et très visibles)
ACTIONS_COLORS = {
    SolverActionType.CLICK: (0, 255, 0),          # Vert vif pour safe
    SolverActionType.FLAG: (255, 0, 0),           # Rouge vif pour flag
    SolverActionType.GUESS: (255, 255, 0),        # Jaune vif pour guess
}


def draw_action_on_image(draw: ImageDraw.ImageDraw, action: SolverAction, px: int, py: int, cell_size: int) -> None:
    """
    Dessine une seule action sur une image avec l'esthétique améliorée.
    
    Args:
        draw: Le contexte de dessin PIL
        action: L'action à dessiner
        px, py: Position en pixels du coin supérieur gauche
        cell_size: Taille de la cellule
    """
    color = ACTIONS_COLORS.get(action.type, (128, 128, 128))
    
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
        # Croix blanche pour les clics sûrs
        draw.line([center_x - cross_size, center_y, center_x + cross_size, center_y], fill=(255, 255, 255), width=3)
        draw.line([center_x, center_y - cross_size, center_x, center_y + cross_size], fill=(255, 255, 255), width=3)
    elif action.type == SolverActionType.FLAG:
        # Point blanc pour les drapeaux
        draw.ellipse([center_x - cross_size//2, center_y - cross_size//2, center_x + cross_size//2, center_y + cross_size//2], fill=(255, 255, 255))


def render_actions_overlay(
    screenshot: Path,
    bounds: Bounds,
    actions: Iterable[SolverAction],
    stride: int,
    cell_size: int,
    output_dir: Path,
) -> Path:
    """
    Dessine les actions proposées par le solver (safe / flag / guess) sur le screenshot donné.
    """
    image = Image.open(screenshot).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, _, _ = bounds

    for action in actions:
        if not action.cell or len(action.cell) != 2:
            continue
        cell_x, cell_y = action.cell
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        
        # Utiliser la fonction centralisée pour dessiner l'action
        draw_action_on_image(draw, action, px, py, cell_size)

    composed = Image.alpha_composite(image, overlay)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{screenshot.stem}_solver_overlay.png"
    composed.save(out_path)
    return out_path
