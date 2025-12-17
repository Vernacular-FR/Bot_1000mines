from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont

from src.lib.s1_capture.s10_overlay_utils import build_overlay_metadata_from_session
from src.lib.s4_solver.facade import SolverAction, SolverActionType
from .s495_historical_canvas import build_historical_canvas_from_canvas, _parse_canvas_name

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

# Couleurs de base (servira pour CSP opaque)
SAFE_COLOR = (0, 255, 0)
CLEANUP_COLOR = (0, 128, 255)  # Bleu pour distinguer les cleanups
FLAG_COLOR = (255, 0, 0)
GUESS_COLOR = (250, 220, 0)

ACTIONS_COLORS = {
    SolverActionType.CLICK: SAFE_COLOR,           # Vert vif pour safe (ou cleanup si taggé)
    SolverActionType.FLAG: FLAG_COLOR,            # Rouge vif pour flag
    SolverActionType.GUESS: GUESS_COLOR,          # Jaune foncé pour guess
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
    is_cleanup = "cleanup" in (getattr(action, "reasoning", "") or "").lower()
    if is_cleanup and action.type == SolverActionType.CLICK:
        color = CLEANUP_COLOR
    else:
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
    screenshot: Optional[Path],
    bounds: Optional[Bounds],
    reducer_actions: Iterable[SolverAction],
    csp_actions: Iterable[SolverAction],
    stride: Optional[int],
    cell_size: Optional[int],
    export_root: Optional[Path],
) -> Optional[Path]:
    """
    Dessine deux couches :
    - actions du FrontiereReducer en transparent
    - actions CSP en opaque
    """
    meta = None
    if not (screenshot and bounds and stride and cell_size and export_root):
        meta = build_overlay_metadata_from_session()
        if not meta:
            return None
        screenshot = Path(meta["screenshot_path"])
        bounds = meta["bounds"]
        stride = meta["stride"]
        cell_size = meta["cell_size"]
        export_root = Path(meta["export_root"])
    else:
        meta = build_overlay_metadata_from_session()

    # Essayer d'utiliser le canvas historique (cumul itératif) comme fond
    if meta:
        current_canvas = Path(meta["screenshot_path"])
        hist_path = build_historical_canvas_from_canvas(current_canvas, Path(meta["export_root"]))
        if hist_path and hist_path.exists():
            screenshot = hist_path
            parsed = _parse_canvas_name(hist_path)
            if parsed:
                _, _, bounds = parsed

    image = Image.open(screenshot).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, _, _ = bounds

    # Actions du reducer (SAFE/FLAG) en premier, très transparents
    reducer_coords = set()
    for action in reducer_actions:
        if not action.cell or len(action.cell) != 2:
            continue
        cell_x, cell_y = action.cell
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw, action, px, py, cell_size, opacity=60)
        reducer_coords.add((cell_x, cell_y))

    # Cleanup en premier (transparent), puis SAFE/FLAG/GUESS opaques
    cleanup_actions = [
        a
        for a in csp_actions
        if "cleanup" in (getattr(a, "reasoning", "") or "").lower()
        and a.cell not in reducer_coords
    ]
    main_actions = [
        a
        for a in csp_actions
        if "cleanup" not in (getattr(a, "reasoning", "") or "").lower()
        and a.cell not in reducer_coords
    ]

    for action in cleanup_actions:
        if not action.cell or len(action.cell) != 2:
            continue
        cell_x, cell_y = action.cell
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw, action, px, py, cell_size, opacity=255)

    for action in main_actions:
        if not action.cell or len(action.cell) != 2:
            continue
        cell_x, cell_y = action.cell
        px = (cell_x - start_x) * stride
        py = (cell_y - start_y) * stride
        draw_action_on_image(draw, action, px, py, cell_size, opacity=255)

    composed = Image.alpha_composite(image, overlay)
    out_dir = Path(export_root) / "s4_solver/s42_solver_overlay"
    out_dir.mkdir(exist_ok=True, parents=True)
    out_path = out_dir / f"{screenshot.stem}_solver_overlay.png"
    composed.save(out_path)

    # Log JSON des actions pour debug (solver)
    try:
        actions_payload = [
            {
                "cell": action.cell,
                "type": getattr(action.type, "name", str(action.type)),
                "reasoning": getattr(action, "reasoning", ""),
                "confidence": getattr(action, "confidence", None),
                "source": "reducer" if action in reducer_actions else "csp_or_cleanup",
            }
            for action in list(reducer_actions) + list(csp_actions)
        ]
        json_dir = out_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        json_path = json_dir / f"{screenshot.stem}_solver_actions.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(actions_payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return out_path
