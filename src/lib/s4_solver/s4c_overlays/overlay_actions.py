"""Overlay des actions du solver (SAFE/FLAG/GUESS)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple, Optional, TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from src.config import CELL_SIZE, CELL_BORDER
from src.lib.s4_solver.types import SolverAction, SolverActionType

if TYPE_CHECKING:
    from src.lib.s0_browser.export_context import ExportContext

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

# Couleurs pour les actions (identiques au legacy)
SAFE_COLOR = (0, 255, 0)                # Vert vif pour safe
CLEANUP_COLOR = (0, 128, 255)           # Bleu pour distinguer les cleanups
FLAG_COLOR = (255, 0, 0)                # Rouge vif pour flag
GUESS_COLOR = (250, 220, 0)             # Jaune foncé pour guess

ACTIONS_COLORS = {
    SolverActionType.SAFE: SAFE_COLOR,
    SolverActionType.FLAG: FLAG_COLOR,
    SolverActionType.GUESS: GUESS_COLOR,
}


def _load_font(size: int = 14):
    """Charge une police avec fallback."""
    for font_name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_action_on_image(
    draw: ImageDraw.ImageDraw,
    action: SolverAction,
    px: int,
    py: int,
    cell_size: int,
    opacity: int = 255,
) -> None:
    """
    Dessine une seule action sur une image (identique au legacy).
    """
    is_cleanup = "cleanup" in (getattr(action, "reasoning", "") or "").lower()
    if is_cleanup and action.action == SolverActionType.SAFE:
        color = CLEANUP_COLOR
    else:
        color = ACTIONS_COLORS.get(action.action, (128, 128, 128))
    color = (*color[:3], opacity)
    
    # Dessiner l'action (carré très visible, sans bordure)
    margin = 2
    draw.rectangle(
        [px + margin, py + margin, px + cell_size - margin, py + cell_size - margin],
        fill=color,
        outline=None,
    )
    
    # Ajouter une croix au centre pour encore plus de visibilité
    center_x = px + cell_size // 2
    center_y = py + cell_size // 2
    cross_size = 8
    
    if action.action == SolverActionType.SAFE:
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
    elif action.action == SolverActionType.FLAG:
        draw.ellipse(
            [
                center_x - cross_size // 2,
                center_y - cross_size // 2,
                center_x + cross_size // 2,
                center_y + cross_size // 2,
            ],
            fill=(255, 255, 255, opacity),
        )
    elif action.action == SolverActionType.GUESS:
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
    base_image: Image.Image,
    actions: List[SolverAction],
    bounds: Bounds,
    stride: Optional[int] = None,
    cell_size: Optional[int] = None,
    reducer_actions: Optional[List[SolverAction]] = None,
) -> Image.Image:
    """
    Dessine les actions du solver sur l'image.
    
    - reducer_actions : actions du propagateur (transparentes)
    - actions : actions principales (opaques)
    """
    stride = stride or (CELL_SIZE + CELL_BORDER)
    cell_size = cell_size or CELL_SIZE
    
    overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    start_x, start_y, _, _ = bounds

    # Actions du reducer (transparentes) en premier
    reducer_coords = set()
    if reducer_actions:
        for action in reducer_actions:
            if not action.coord or len(action.coord) != 2:
                continue
            cell_x, cell_y = action.coord
            px = (cell_x - start_x) * stride
            py = (cell_y - start_y) * stride
            draw_action_on_image(draw, action, px, py, cell_size, opacity=60)
            reducer_coords.add((cell_x, cell_y))

    def _is_sweep(act: SolverAction) -> bool:
        """Identifie une action de sweep (ex-cleanup bonus) pour ne pas l'afficher ici."""
        return "sweep" in (getattr(act, "reasoning", "") or "").lower()

    # Séparer cleanups et actions principales (en excluant les sweep)
    cleanup_actions = [
        a for a in actions
        if "cleanup" in (getattr(a, "reasoning", "") or "").lower()
        and a.coord not in reducer_coords
        and not _is_sweep(a)
    ]
    main_actions = [
        a for a in actions
        if "cleanup" not in (getattr(a, "reasoning", "") or "").lower()
        and a.coord not in reducer_coords
        and not _is_sweep(a)
    ]

    # Cleanup (opaques)
    for action in cleanup_actions:
        if not action.coord or len(action.coord) != 2:
            continue
        cell_x, cell_y = action.coord
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw, action, px, py, cell_size, opacity=255)

    # Actions principales (opaques)
    for action in main_actions:
        if not action.coord or len(action.coord) != 2:
            continue
        cell_x, cell_y = action.coord
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw, action, px, py, cell_size, opacity=255)

    return Image.alpha_composite(base_image.convert("RGBA"), overlay)


def render_and_save_actions(
    base_image: Image.Image,
    actions: List[SolverAction],
    export_ctx: "ExportContext",
    bounds: Optional[Bounds] = None,
    stride: Optional[int] = None,
    reducer_actions: Optional[List[SolverAction]] = None,
) -> Optional[Path]:
    """Render et sauvegarde l'overlay des actions."""
    if not export_ctx.overlay_enabled:
        return None
    
    bounds = bounds or export_ctx.capture_bounds
    if bounds is None:
        return None
    
    stride = stride or export_ctx.capture_stride or (CELL_SIZE + CELL_BORDER)
    
    overlay_img = render_actions_overlay(
        base_image, actions, bounds, stride, 
        reducer_actions=reducer_actions
    )
    
    out_path = export_ctx.solver_overlay_path("s4c2_actions")
    # Optimisation PNG : compression et optimisation activées
    overlay_img.save(out_path, optimize=True, compress_level=6)
    
    # Export JSON associé
    _save_json(actions, export_ctx, bounds, stride, reducer_actions)
    
    return out_path


def _save_json(
    actions: List[SolverAction],
    export_ctx: "ExportContext",
    bounds: Bounds,
    stride: int,
    reducer_actions: Optional[List[SolverAction]] = None,
) -> Optional[Path]:
    """Sauvegarde les métadonnées des actions en JSON."""
    all_actions = list(actions) + (reducer_actions or [])
    
    actions_payload = [
        {
            "coord": action.coord,
            "type": getattr(action.action, "name", str(action.action)),
            "reasoning": getattr(action, "reasoning", ""),
            "confidence": getattr(action, "confidence", None),
            "source": "reducer" if reducer_actions and action in reducer_actions else "main",
        }
        for action in all_actions
    ]
    
    payload = {
        "iteration": export_ctx.iteration,
        "game_id": export_ctx.game_id,
        "bounds": bounds,
        "stride": stride,
        "action_count": len(all_actions),
        "actions": actions_payload,
    }
    
    json_path = export_ctx.json_path("s4c2_actions", "actions")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    
    return json_path
