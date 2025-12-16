from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .facade import CaptureControllerApi, CaptureRequest, CaptureResult
from .s11_canvas_capture import CanvasCaptureBackend
from src.lib.s0_interface.facade import InterfaceControllerApi


@dataclass
class CaptureController(CaptureControllerApi):
    interface: InterfaceControllerApi
    canvas_backend: CanvasCaptureBackend
    viewport_mapper: Optional[object] = None

    def capture_zone(self, request: CaptureRequest) -> CaptureResult:
        capture_meta = self.interface.get_capture_meta(
            request.canvas_point[0],
            request.canvas_point[1],
        )
        if not capture_meta:
            raise RuntimeError("Impossible d'obtenir les métadonnées de capture.")

        relative_origin = self._compute_relative_origin(request, capture_meta)
        capture = self.canvas_backend.capture_tile(
            canvas_id=capture_meta["canvas_id"],
            relative_origin=relative_origin,
            size=request.size,
            save=request.save,
            filename=request.filename,
            bucket=request.bucket,
            metadata=request.metadata,
        )

        return CaptureResult(
            image=capture.image,
            raw_bytes=capture.raw_bytes,
            width=capture.width,
            height=capture.height,
            saved_path=capture.saved_path,
            metadata=capture.metadata,
        )

    def capture_grid_window(
        self,
        grid_bounds: Tuple[int, int, int, int],
        *,
        save: bool = False,
        annotate: bool = False,
        filename: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> CaptureResult:
        _ = annotate
        self.interface.ensure_visible(grid_bounds)
        left, top, right, bottom = grid_bounds
        width = (right - left + 1) * self.interface.converter.cell_total
        height = (bottom - top + 1) * self.interface.converter.cell_total
        request = CaptureRequest(
            canvas_point=(left * self.interface.converter.cell_total, top * self.interface.converter.cell_total),
            size=(width, height),
            save=save,
            filename=filename,
            bucket=bucket,
        )
        return self.capture_zone(request)

    @staticmethod
    def _compute_relative_origin(
        request: CaptureRequest,
        capture_meta: Dict[str, Tuple[int, int]],
    ) -> Tuple[int, int]:
        tile_origin_x, tile_origin_y = capture_meta["relative_origin"]
        offset_x = int(request.canvas_point[0] - tile_origin_x)
        offset_y = int(request.canvas_point[1] - tile_origin_y)

        if offset_x < 0 or offset_y < 0:
            raise ValueError("La zone demandée déborde du canvas sélectionné.")

        tile_width, tile_height = capture_meta["size"]
        if offset_x + request.size[0] > tile_width or offset_y + request.size[1] > tile_height:
            raise ValueError("La zone demandée dépasse les limites de la tuile canvas.")

        return offset_x, offset_y
