from __future__ import annotations

from typing import Dict, Optional, Tuple

from src.config import CELL_SIZE, CELL_BORDER
from src.lib.s3_storage.s30_session_context import (
    get_session_context,
    set_session_context,
    update_capture_metadata,
)


def build_overlay_metadata_from_session(
    *,
    bounds: Optional[Tuple[int, int, int, int]] = None,
    stride: Optional[int] = None,
    cell_size: Optional[int] = None,
) -> Dict:
    """
    Construit un dict overlay (export_root, screenshot_path, bounds, stride, cell_size)
    à partir du SessionContext. Retourne {} si les infos essentielles manquent.
    Placé côté capture car ces métadonnées décrivent la capture produite.
    """
    ctx = get_session_context()
    if not (ctx.overlay_enabled and ctx.export_root and ctx.capture_saved_path):
        return {}
    resolved_bounds = bounds or ctx.capture_bounds
    resolved_stride = stride or ctx.capture_stride or (CELL_SIZE + CELL_BORDER)
    resolved_cell_size = cell_size or CELL_SIZE
    if not (resolved_bounds and resolved_stride and resolved_cell_size):
        return {}
    return {
        "export_root": ctx.export_root,
        "screenshot_path": ctx.capture_saved_path,
        "bounds": resolved_bounds,
        "stride": resolved_stride,
        "cell_size": resolved_cell_size,
    }


def setup_overlay_context(
    *,
    export_root: str | None,
    screenshot_path: str,
    bounds: Tuple[int, int, int, int],
    stride: int,
    game_id: str = "test",
    iteration: int = 0,
    overlay_enabled: bool = True,
) -> None:
    """
    Helper pour scripts/tests : publie SessionContext (IDs + overlay_enabled + export_root)
    et capture (path, bounds, stride).
    """
    set_session_context(
        game_id=game_id,
        iteration=iteration,
        export_root=export_root or "",
        overlay_enabled=overlay_enabled,
    )
    update_capture_metadata(
        saved_path=screenshot_path,
        bounds=bounds,
        stride=stride,
    )
