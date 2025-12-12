#!/usr/bin/env python3
"""
Service métier s1 – capture de zones via InterfaceController/CaptureController.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.lib.s1_capture import CaptureResult
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
