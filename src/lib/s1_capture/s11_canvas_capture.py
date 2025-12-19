from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple, Any

from PIL import Image
from selenium.webdriver.remote.webdriver import WebDriver

from src.config import PATHS


@dataclass
class CanvasCaptureResult:
    """Résultat brut d'une capture canvas."""

    image: Image.Image
    raw_bytes: bytes
    width: int
    height: int
    saved_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CanvasCaptureBackend:
    """
    Capture directe via `canvas.toDataURL()`.
    - Pas de capture plein écran.
    - Les sauvegardes disque sont optionnelles et centralisées.
    """

    def __init__(
        self,
        driver: WebDriver,
        paths: Optional[Dict[str, str]] = None,
        default_bucket: str = "grid",
    ):
        self.driver = driver
        self.paths = paths or PATHS
        self.default_bucket = default_bucket
        self._ensure_directories()

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    def capture_tile(
        self,
        *,
        canvas_id: str,
        relative_origin: Tuple[float, float],
        size: Tuple[int, int],
        save: bool = False,
        filename: Optional[str] = None,
        bucket: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CanvasCaptureResult:
        """
        Capture une sous-zone d'une tuile canvas.
        Args:
            canvas_id: identifiant DOM de la tuile (`CanvasLocator`/InterfaceController).
            relative_origin: (x, y) en pixels à l'intérieur de la tuile.
            size: (width, height) en pixels.
            save: si True, sauvegarde PNG sur disque.
            filename: nom de fichier optionnel (sinon timestamp).
            bucket: clé PATHS pour la sauvegarde (par défaut `self.default_bucket`).
            metadata: informations additionnelles retournées avec le résultat.
        """
        if size[0] <= 0 or size[1] <= 0:
            raise ValueError("La taille de capture doit être strictement positive.")

        data_url = self._execute_canvas_capture(canvas_id, relative_origin, size)
        image = self._data_url_to_image(data_url)

        saved_path = None
        if save:
            saved_path = self._save_image(image, filename=filename, bucket=bucket)

        return CanvasCaptureResult(
            image=image,
            raw_bytes=self._image_to_bytes(image),
            width=image.width,
            height=image.height,
            saved_path=saved_path,
            metadata=metadata,
        )

    # ------------------------------------------------------------------ #
    # JavaScript bridge                                                  #
    # ------------------------------------------------------------------ #

    def _execute_canvas_capture(
        self,
        canvas_id: str,
        relative_origin: Tuple[float, float],
        size: Tuple[int, int],
    ) -> str:
        script = """
        const canvasId = arguments[0];
        const offset = arguments[1];
        const targetSize = arguments[2];

        const resolveCanvas = () => {
            const byId = document.getElementById(canvasId);
            if (byId) return byId;
            return document.querySelector(`canvas[data-tile-id="${canvasId}"]`) ||
                   document.querySelector(`canvas[id="${canvasId}"]`);
        };

        const sourceCanvas = resolveCanvas();
        if (!sourceCanvas) {
            return { success: false, error: `Canvas ${canvasId} introuvable` };
        }

        const [offsetX, offsetY] = offset;
        const [cropWidth, cropHeight] = targetSize;

        const clone = document.createElement('canvas');
        clone.width = cropWidth;
        clone.height = cropHeight;
        const ctx = clone.getContext('2d');
        ctx.drawImage(
            sourceCanvas,
            offsetX, offsetY, cropWidth, cropHeight,
            0, 0, cropWidth, cropHeight
        );
        return { success: true, dataURL: clone.toDataURL('image/png') };
        """

        response = self.driver.execute_script(
            script,
            canvas_id,
            (float(relative_origin[0]), float(relative_origin[1])),
            (int(size[0]), int(size[1])),
        )

        if not response or not response.get("success"):
            error = response.get("error") if isinstance(response, dict) else "Réponse JS invalide"
            raise RuntimeError(f"Capture canvas échouée ({canvas_id}): {error}")

        return response["dataURL"]

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _ensure_directories(self):
        for key, path in self.paths.items():
            if key in {"metadata", "grid_db"}:
                continue
            os.makedirs(path, exist_ok=True)

    @staticmethod
    def _data_url_to_image(data_url: str) -> Image.Image:
        if not data_url.startswith("data:image/png;base64,"):
            raise ValueError("DataURL inattendu (PNG attendu).")
        base64_data = data_url.split(",", 1)[1]
        raw_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

        # Les canvases 1000mines possèdent un fond transparent -> forcer un fond blanc.
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
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _save_image(
        self,
        image: Image.Image,
        *,
        filename: Optional[str],
        bucket: Optional[str],
    ) -> str:
        # Si bucket est un chemin complet (contient des séparateurs), l'utiliser directement
        if bucket and ("/" in bucket or "\\" in bucket):
            target_dir = bucket
        else:
            target_dir = self.paths.get(bucket or self.default_bucket, "temp/s1_capture")
        
        os.makedirs(target_dir, exist_ok=True)
        resolved_filename = filename or self._build_filename()
        path = os.path.join(target_dir, resolved_filename)
        image.save(path, format="PNG")
        return path

    @staticmethod
    def _build_filename(prefix: str = "capture") -> str:
        return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
