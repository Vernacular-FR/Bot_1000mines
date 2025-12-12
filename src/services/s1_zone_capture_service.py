#!/usr/bin/env python3
"""
Service métier s1 – capture de zones via InterfaceController/CaptureController.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.lib.s0_interface.s03_Coordonate_system import CanvasLocator
from src.lib.s1_capture import CaptureResult
from src.lib.s1_capture.s11_canvas_capture import CanvasCaptureBackend
from src.lib.s1_capture.s12_canvas_compositor import compose_aligned_grid
from src.lib.s0_interface.controller import InterfaceController


@dataclass
class GridCapture:
    """Objet combinant le résultat de capture et les métadonnées nécessaires aux étapes suivantes."""

    result: CaptureResult
    grid_bounds: Tuple[int, int, int, int]
    cell_stride: int


class ZoneCaptureService:
    """
    Façade métier pour orchestrer les captures basées sur InterfaceController.
    - S’appuie sur `interface.capture_grid_window` (lib/s1_capture) pour éviter toute redondance.
    - Fournit des métadonnées prêtes à être consommées par la vision (grid_bounds + stride).
    """

    def __init__(self, interface: InterfaceController):
        self.interface = interface
        self.cell_stride = interface.converter.cell_total

    def capture_grid_window(
        self,
        grid_bounds: Tuple[int, int, int, int],
        *,
        save: bool = False,
        annotate: bool = False,
        filename: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> GridCapture:
        capture = self.interface.capture_grid_window(
            grid_bounds,
            save=save,
            annotate=annotate,
            filename=filename,
            bucket=bucket,
        )
        metadata = capture.metadata or {}
        metadata.update(
            {
                "grid_bounds": grid_bounds,
                "cell_stride": self.cell_stride,
            }
        )
        capture.metadata = metadata
        return GridCapture(result=capture, grid_bounds=grid_bounds, cell_stride=self.cell_stride)

    def compose_from_canvas_tiles(
        self,
        *,
        captures: List[Dict],
        grid_reference: tuple[int, int],
        save_dir: Path,
    ) -> GridCapture:
        """
        Assemble plusieurs tuiles canvas (captures brutes) en une capture alignée sur la grille.
        """
        capture_result, grid_bounds = compose_aligned_grid(
            captures=captures,
            grid_reference=grid_reference,
            cell_stride=self.cell_stride,
            save_dir=save_dir,
        )
        return GridCapture(
            result=capture_result,
            grid_bounds=grid_bounds,
            cell_stride=self.cell_stride,
        )

    def capture_canvas_tiles(
        self,
        *,
        locator: CanvasLocator,
        backend: CanvasCaptureBackend,
        out_dir: Path,
        game_id: str | None = None,
    ) -> List[Dict]:
        """
        Capture toutes les tuiles canvas visibles et sauvegarde les PNG bruts.
        """
        descriptors = locator.locate_all()
        game_info = f" pour le jeu {game_id}" if game_id else ""
        print(f"[CANVAS] {len(descriptors)} canvas trouvés{game_info}.")

        out_dir.mkdir(parents=True, exist_ok=True)

        captures: List[Dict] = []
        for desc in descriptors:
            cid = desc["id"]
            try:
                result = backend.capture_tile(
                    canvas_id=cid,
                    relative_origin=(0, 0),
                    size=(512, 512),
                    save=True,
                    filename=f"raw_canvas_{cid}.png",
                    bucket=str(out_dir),
                    metadata={"tile_descriptor": desc},
                )
                print(f"[CANVAS] {cid} → {result.saved_path}")
                captures.append({"descriptor": desc, "capture": result})
            except Exception as exc:
                print(f"[CANVAS] Erreur {cid}: {exc}")

        return captures
