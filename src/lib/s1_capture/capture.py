"""Capture des canvas via toDataURL et composition alignée."""

from __future__ import annotations

import base64
import io
import os
import time
import math
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from PIL import Image
from selenium.webdriver.remote.webdriver import WebDriver

from src.config import CELL_SIZE, CELL_BORDER, GRID_REFERENCE_POINT
from src.lib.s0_coordinates import CanvasLocator
from src.lib.s0_coordinates.types import GridBounds
from .types import CaptureInput, CaptureResult, CanvasCaptureResult
from ..s0_coordinates.types import GridBounds

class CanvasCaptureBackend:
    """Capture directe via canvas.toDataURL() (in-memory only, jamais de fichiers)."""

    def __init__(self, driver: WebDriver, default_save_dir: Optional[str] = None):
        self.driver = driver
        # Pas de sauvegarde disque des raws
        self.default_save_dir = None

    def capture_tile(
        self,
        canvas_id: str,
        save: bool = False,
        save_dir: Optional[str] = None,
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CanvasCaptureResult:
        """Capture un canvas complet (en mémoire uniquement)."""
        data_url = self._execute_canvas_capture(canvas_id)
        image = self._data_url_to_image(data_url)
        raw_bytes = self._image_to_bytes(image)

        # Raws jamais sauvegardés
        return CanvasCaptureResult(
            image=image,
            raw_bytes=raw_bytes,
            width=image.width,
            height=image.height,
            canvas_id=canvas_id,
            saved_path=None,
            metadata=metadata,
        )

    def _execute_canvas_capture(self, canvas_id: str) -> str:
        """Exécute le script JS pour capturer le canvas."""
        script = """
        const canvasId = arguments[0];
        const sourceCanvas = document.getElementById(canvasId) ||
                            document.querySelector(`canvas[data-tile-id="${canvasId}"]`);
        if (!sourceCanvas) {
            return { success: false, error: `Canvas ${canvasId} introuvable` };
        }
        return { success: true, dataURL: sourceCanvas.toDataURL('image/png') };
        """
        response = self.driver.execute_script(script, canvas_id)

        if not response or not response.get("success"):
            error = response.get("error") if isinstance(response, dict) else "Réponse JS invalide"
            raise RuntimeError(f"Capture canvas échouée ({canvas_id}): {error}")

        return response["dataURL"]

    @staticmethod
    def _data_url_to_image(data_url: str) -> Image.Image:
        """Convertit un dataURL en image PIL."""
        if not data_url.startswith("data:image/png;base64,"):
            raise ValueError("DataURL inattendu (PNG attendu).")
        base64_data = data_url.split(",", 1)[1]
        raw_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

        # Fond transparent -> forcer fond blanc
        if "A" in image.getbands():
            alpha = image.split()[-1]
            background = Image.new("RGBA", image.size, (255, 255, 255, 255))
            background.paste(image, mask=alpha)
            image = background.convert("RGB")
        else:
            image = image.convert("RGB")

        return image

    @staticmethod
    def _image_to_bytes(image: Image.Image) -> bytes:
        """Convertit une image PIL en bytes PNG."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _save_image(self, image: Image.Image, save_dir: str, filename: str) -> str:
        """Sauvegarde l'image sur disque."""
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, filename)
        image.save(path, format="PNG")
        return path


def _compose_aligned_grid(
    captures: List[CanvasCaptureResult],
    grid_reference: Tuple[int, int],
    cell_stride: int,
    save: bool,
    save_dir: Optional[Path] = None,
) -> Tuple[CaptureResult, Tuple[int, int, int, int]]:
    """
    Assemble les tuiles canvas en un composite aligné sur les cellules Minesweeper,
    et calcule les bornes de grille couvertes.
    """
    if save and save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    min_left = min(item.metadata["canvas_info"].relative_left for item in captures)
    min_top = min(item.metadata["canvas_info"].relative_top for item in captures)
    max_right = max(
        item.metadata["canvas_info"].relative_left + item.metadata["canvas_info"].width
        for item in captures
    )
    max_bottom = max(
        item.metadata["canvas_info"].relative_top + item.metadata["canvas_info"].height
        for item in captures
    )

    width = int(math.ceil(max_right - min_left))
    height = int(math.ceil(max_bottom - min_top))
    composite = Image.new("RGB", (width, height), "white")

    for item in captures:
        desc = item.metadata["canvas_info"]
        offset_x = int(round(desc.relative_left - min_left))
        offset_y = int(round(desc.relative_top - min_top))
        composite.paste(item.image, (offset_x, offset_y))

    ref_x, ref_y = grid_reference
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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    composite_path = None
    if save and save_dir:
        composite_path = save_dir / f"full_grid_{timestamp}.png"
        grid_image.save(composite_path, format="PNG")

    buffer = io.BytesIO()
    grid_image.save(buffer, format="PNG")
    composite_bytes = buffer.getvalue()
    actual_canvas_left = min_left + crop_left
    actual_canvas_top = min_top + crop_top
    actual_canvas_right = min_left + crop_right
    actual_canvas_bottom = min_top + crop_bottom

    grid_bounds = (
        int(math.floor((actual_canvas_left - ref_x) / cell_stride)),
        int(math.floor((actual_canvas_top - ref_y) / cell_stride)),
        int(math.ceil((actual_canvas_right - ref_x) / cell_stride)) - 1,
        int(math.ceil((actual_canvas_bottom - ref_y) / cell_stride)) - 1,
    )
    
    print(f"[COMPOSITE] Bounds calculés: {grid_bounds}")
    print(f"[COMPOSITE] Taille composite: {grid_image.width}x{grid_image.height}")

    capture_result = CaptureResult(
        captures=captures,
        grid_bounds=None,
        timestamp=time.time(),
        metadata={
            "composite_path": str(composite_path),
            "cell_stride": cell_stride,
            "grid_bounds": grid_bounds,
            "composite_bytes": composite_bytes,
        },
    )

    return capture_result, grid_bounds


def capture_all_canvases(
    driver: WebDriver,
    save: bool = False,
    save_dir: Optional[str] = None,
    game_id: Optional[str] = None,
) -> CaptureResult:
    """Capture tous les canvas visibles et compose une grille alignée."""
    locator = CanvasLocator(driver=driver)
    backend = CanvasCaptureBackend(driver=driver)

    canvas_infos = locator.locate_all()
    game_info = f" pour le jeu {game_id}" if game_id else ""
    print(f"[CANVAS] {len(canvas_infos)} canvas trouvés{game_info}.")

    captures: List[CanvasCaptureResult] = []
    for info in canvas_infos:
        # Tentative de capture avec retry (le DOM peut changer pendant la boucle)
        success = False
        for attempt in range(3):
            try:
                result = backend.capture_tile(
                    canvas_id=info.id,
                    save=False,
                    save_dir=None,
                    filename=None,
                    metadata={"canvas_info": info},
                )
                captures.append(result)
                success = True
                break
            except Exception:
                if attempt < 2:
                    time.sleep(0.05) # Petite pause avant retry
                continue
        
        if not success:
            print(f"[CANVAS] Échec capture définitive pour {info.id} après 3 tentatives.")

    composite_result, grid_bounds = _compose_aligned_grid(
        captures=captures,
        grid_reference=GRID_REFERENCE_POINT,
        cell_stride=CELL_SIZE + CELL_BORDER,
        save=False,
        save_dir=None,
    )

    gb_obj = GridBounds(
        min_row=grid_bounds[1],
        min_col=grid_bounds[0],
        max_row=grid_bounds[3],
        max_col=grid_bounds[2],
    )

    return CaptureResult(
        captures=captures,
        grid_bounds=gb_obj,
        timestamp=time.time(),
        metadata={
            "game_id": game_id,
            "canvas_count": len(captures),
            "composite_path": composite_result.metadata.get("composite_path"),
            "composite_bytes": composite_result.metadata.get("composite_bytes"),
            "grid_bounds": gb_obj,  # Directly use the GridBounds object
        },
    )


def capture_canvas(input: CaptureInput) -> CaptureResult:
    """Point d'entrée principal pour la capture."""
    return capture_all_canvases(
        driver=input.driver,
        save=input.save_dir is not None,
        save_dir=input.save_dir,
        game_id=input.game_id,
    )
