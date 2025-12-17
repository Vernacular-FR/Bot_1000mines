from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageChops


def _parse_canvas_name(path: Path) -> Optional[Tuple[str, int, Tuple[int, int, int, int]]]:
    """
    Parse un nom de fichier de canvas : {game}_iter{n}_{xmin}_{ymin}_{xmax}_{ymax}[...].png
    Retourne (game_id, iter, bounds) ou None.
    """
    m = re.match(r"(.*)_iter(\d+)_(-?\d+)_(-?\d+)_(-?\d+)_(-?\d+)", path.stem)
    if not m:
        return None
    game_id = m.group(1)
    iter_id = int(m.group(2))
    bounds = (int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)))
    return game_id, iter_id, bounds


def build_historical_canvas_from_canvas(
    canvas_path: Path,
    export_root: Path,
    fade_alpha: int = 10,
) -> Optional[Path]:
    """
    Construit/actualise un canvas historique en superposant l'image `canvas_path`
    sur le canvas historique précédent (s1_historical_canvas), en ajoutant un voile gris
    pour distinguer l’ancien.
    - Utilise le même stride et les mêmes bounds que le canvas courant pour l’alignement.
    - Le fichier historique est nommé comme un canvas standard avec suffixe `_hist`.
    """
    if not canvas_path.exists():
        return None

    parsed = _parse_canvas_name(canvas_path)
    if not parsed:
        return None
    game_id, iter_id, bounds = parsed
    xmin, ymin, xmax, ymax = bounds

    # Charger le canvas courant
    current = Image.open(canvas_path).convert("RGBA")
    cur_w, cur_h = current.size
    stride_x = max(1, cur_w // max(1, xmax - xmin))
    stride_y = max(1, cur_h // max(1, ymax - ymin))
    stride = stride_x  # on suppose carré

    # Chercher l’histo précédent
    hist_dir = Path(export_root) / "s4_solver/s40_historical_canvas"
    hist_dir.mkdir(parents=True, exist_ok=True)
    prev_hist = None
    prev_bounds = None
    for p in sorted(hist_dir.glob("*_hist.png")):
        parsed_prev = _parse_canvas_name(p)
        if not parsed_prev:
            continue
        _, prev_iter, b = parsed_prev
        if prev_iter == iter_id - 1:
            prev_hist = p
            prev_bounds = b
    # Déterminer les bounds cumulés
    if prev_bounds:
        pxmin, pymin, pxmax, pymax = prev_bounds
        union_bounds = (min(xmin, pxmin), min(ymin, pymin), max(xmax, pxmax), max(ymax, pymax))
    else:
        union_bounds = bounds
    uxmin, uymin, uxmax, uymax = union_bounds
    canvas_w = (uxmax - uxmin) * stride
    canvas_h = (uymax - uymin) * stride

    base = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))

    # Coller l’ancien (avec voile gris) si présent
    if prev_hist and prev_hist.exists():
        old = Image.open(prev_hist).convert("RGBA")
        # Voile gris pour marquer l’historique
        gray = Image.new("RGBA", old.size, (0, 0, 0, fade_alpha))
        old = Image.alpha_composite(old, gray)
        px_offset = (prev_bounds[0] - uxmin) * stride
        py_offset = (prev_bounds[1] - uymin) * stride
        base.paste(old, (px_offset, py_offset), old)

    # Coller le canvas courant
    cx_offset = (xmin - uxmin) * stride
    cy_offset = (ymin - uymin) * stride
    base.paste(current, (cx_offset, cy_offset), current)

    out_name = f"{game_id}_iter{iter_id}_{uxmin}_{uymin}_{uxmax}_{uymax}_hist.png"
    out_path = hist_dir / out_name
    base.save(out_path)
    return out_path
