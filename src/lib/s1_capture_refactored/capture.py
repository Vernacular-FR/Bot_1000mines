"""Capture canvas via toDataURL."""

import base64
import io
import os
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from PIL import Image
from selenium.webdriver.remote.webdriver import WebDriver

from .types import CaptureInput, CaptureResult


class CanvasCaptureBackend:
    """Capture directe via canvas.toDataURL()."""

    def __init__(self, driver: WebDriver, default_save_dir: str = "temp/captures"):
        self.driver = driver
        self.default_save_dir = default_save_dir

    def set_driver(self, driver: WebDriver) -> None:
        """Configure le driver."""
        self.driver = driver

    def capture(self, input: CaptureInput) -> CaptureResult:
        """Capture une zone d'un canvas."""
        if input.size[0] <= 0 or input.size[1] <= 0:
            raise ValueError("La taille de capture doit être strictement positive.")

        timestamp = time.time()
        data_url = self._execute_canvas_capture(
            input.canvas_id, input.relative_origin, input.size
        )
        image = self._data_url_to_image(data_url)

        saved_path = None
        if input.save:
            saved_path = self._save_image(
                image, filename=input.filename, bucket=input.bucket
            )

        return CaptureResult(
            image=image,
            raw_bytes=self._image_to_bytes(image),
            width=image.width,
            height=image.height,
            timestamp=timestamp,
            saved_path=saved_path,
            metadata=input.metadata,
        )

    def _execute_canvas_capture(
        self,
        canvas_id: str,
        relative_origin: Tuple[float, float],
        size: Tuple[int, int],
    ) -> str:
        """Exécute le script JS pour capturer le canvas."""
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

    @staticmethod
    def _data_url_to_image(data_url: str) -> Image.Image:
        """Convertit un dataURL en image PIL."""
        if not data_url.startswith("data:image/png;base64,"):
            raise ValueError("DataURL inattendu (PNG attendu).")
        
        base64_data = data_url.split(",", 1)[1]
        raw_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

        # Fond transparent → fond blanc
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

    def _save_image(
        self,
        image: Image.Image,
        filename: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> str:
        """Sauvegarde l'image sur disque."""
        if bucket and ("/" in bucket or "\\" in bucket):
            target_dir = bucket
        else:
            target_dir = bucket or self.default_save_dir

        os.makedirs(target_dir, exist_ok=True)
        resolved_filename = filename or f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        path = os.path.join(target_dir, resolved_filename)
        image.save(path, format="PNG")
        return path


# === Fonctions standalone (API fonctionnelle) ===

_default_backend: Optional[CanvasCaptureBackend] = None


def _get_backend() -> CanvasCaptureBackend:
    global _default_backend
    if _default_backend is None:
        _default_backend = CanvasCaptureBackend(driver=None)
    return _default_backend


def set_capture_driver(driver: WebDriver) -> None:
    """Configure le driver pour le backend par défaut."""
    _get_backend().set_driver(driver)


def capture_canvas(input: CaptureInput) -> CaptureResult:
    """Capture une zone d'un canvas."""
    return _get_backend().capture(input)


def capture_zone(
    canvas_id: str,
    relative_origin: Tuple[float, float],
    size: Tuple[int, int],
    save: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> CaptureResult:
    """Capture une zone (API simplifiée)."""
    input = CaptureInput(
        canvas_id=canvas_id,
        relative_origin=relative_origin,
        size=size,
        save=save,
        metadata=metadata,
    )
    return _get_backend().capture(input)
