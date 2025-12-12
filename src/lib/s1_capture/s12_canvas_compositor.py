from __future__ import annotations

import io
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image

from src.lib.s1_capture import CaptureResult


def compose_aligned_grid(
    *,
    captures: List[Dict],
    grid_reference: tuple[int, int],
    cell_stride: int,
    save_dir: Path,
) -> Tuple[CaptureResult, Tuple[int, int, int, int]]:
    """
    Assemble plusieurs tuiles canvas en un composite aligné sur les cellules Minesweeper.
    Retourne un CaptureResult prêt pour la vision + les limites de grille couvertes.
    """
    save_dir.mkdir(parents=True, exist_ok=True)

    min_left = min(desc["descriptor"]["relative_left"] for desc in captures)
    min_top = min(desc["descriptor"]["relative_top"] for desc in captures)
    max_right = max(
        desc["descriptor"]["relative_left"] + desc["descriptor"]["width"] for desc in captures
    )
    max_bottom = max(
        desc["descriptor"]["relative_top"] + desc["descriptor"]["height"] for desc in captures
    )

    width = int(math.ceil(max_right - min_left))
    height = int(math.ceil(max_bottom - min_top))
    composite = Image.new("RGB", (width, height), "white")

    for item in captures:
        desc = item["descriptor"]
        capture = item["capture"]
        offset_x = int(round(desc["relative_left"] - min_left))
        offset_y = int(round(desc["relative_top"] - min_top))
        composite.paste(capture.image, (offset_x, offset_y))

    ref_x, ref_y = grid_reference

    # grid_reference=(-1,-1) pointe sur la bordure.
    # Pour aligner les cellules (0,0 modulo stride) on corrige avec +1.
    cell_ref_x = ref_x + 1
    cell_ref_y = ref_y + 1

    grid_left = int(math.ceil((min_left - cell_ref_x) / cell_stride))
    grid_top = int(math.ceil((min_top - cell_ref_y) / cell_stride))
    grid_right = int(math.floor((max_right - cell_ref_x) / cell_stride)) - 1
    grid_bottom = int(math.floor((max_bottom - cell_ref_y) / cell_stride)) - 1

    if grid_left > grid_right or grid_top > grid_bottom:
        raise RuntimeError("Impossible de déterminer une zone grille alignée complète à partir des canvases.")

    aligned_left_px = grid_left * cell_stride + cell_ref_x
    aligned_top_px = grid_top * cell_stride + cell_ref_y
    aligned_right_px = (grid_right + 1) * cell_stride + cell_ref_x
    aligned_bottom_px = (grid_bottom + 1) * cell_stride + cell_ref_y

    crop_left = int(round(aligned_left_px - min_left))
    crop_top = int(round(aligned_top_px - min_top))
    crop_right = int(round(aligned_right_px - min_left))
    crop_bottom = int(round(aligned_bottom_px - min_top))

    grid_image = composite.crop((crop_left, crop_top, crop_right, crop_bottom))

    final_width = crop_right - crop_left
    final_height = crop_bottom - crop_top
    assert final_width % cell_stride == 0, f"Largeur non alignée: {final_width} % {cell_stride} = {final_width % cell_stride}"
    assert final_height % cell_stride == 0, f"Hauteur non alignée: {final_height} % {cell_stride} = {final_height % cell_stride}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    composite_path = save_dir / f"full_grid_{timestamp}.png"
    grid_image.save(composite_path, format="PNG")

    buffer = io.BytesIO()
    grid_image.save(buffer, format="PNG")

    actual_canvas_left = min_left + crop_left
    actual_canvas_top = min_top + crop_top
    actual_canvas_right = min_left + crop_right
    actual_canvas_bottom = min_top + crop_bottom

    actual_grid_left = int(math.floor((actual_canvas_left - ref_x) / cell_stride))
    actual_grid_top = int(math.floor((actual_canvas_top - ref_y) / cell_stride))
    actual_grid_right = int(math.ceil((actual_canvas_right - ref_x) / cell_stride)) - 1
    actual_grid_bottom = int(math.ceil((actual_canvas_bottom - ref_y) / cell_stride)) - 1

    grid_bounds = (
        actual_grid_left,
        actual_grid_top,
        actual_grid_right,
        actual_grid_bottom,
    )

    capture_result = CaptureResult(
        image=grid_image,
        raw_bytes=buffer.getvalue(),
        width=grid_image.width,
        height=grid_image.height,
        saved_path=str(composite_path),
        metadata={"grid_bounds": grid_bounds, "cell_stride": cell_stride},
    )

    return capture_result, grid_bounds
