"""Localisation des canvas (512×512) autour de #anchor."""

import re
from typing import List, Tuple, Optional, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver

from .types import CanvasInfo


class CanvasLocator:
    """Localise les canvases et renvoie leurs offsets absolus/relatifs."""

    TILE_ID_PATTERN = re.compile(r"(?P<x>-?\d+)x(?P<y>-?\d+)")

    def __init__(
        self,
        driver: WebDriver = None,
        anchor_selector: str = "#anchor",
        canvas_selector: str = "canvas",
    ):
        self.driver = driver
        self.anchor_selector = anchor_selector
        self.canvas_selector = canvas_selector
        self._anchor_element = None
        self._anchor_rect_cache = None
        self._descriptors_cache: Optional[List[CanvasInfo]] = None

    def set_driver(self, driver: WebDriver) -> None:
        """Configure le driver et reset les caches."""
        self.driver = driver
        self._anchor_element = None
        self._anchor_rect_cache = None
        self._descriptors_cache = None

    def _require_driver(self) -> None:
        if not self.driver:
            raise RuntimeError("Driver non initialisé pour CanvasLocator")

    def _get_anchor_element(self):
        self._require_driver()
        if not self._anchor_element:
            self._anchor_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.anchor_selector))
            )
        return self._anchor_element

    def _get_anchor_rect(self) -> Dict:
        if self._anchor_rect_cache is None:
            self._anchor_rect_cache = self._element_rect(self._get_anchor_element())
        return self._anchor_rect_cache

    def _element_rect(self, element) -> Dict:
        script = """
        const el = arguments[0];
        const rect = el.getBoundingClientRect();
        return {
            left: rect.left,
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
            width: rect.width,
            height: rect.height
        };
        """
        return self.driver.execute_script(script, element)

    def _parse_tile_id(self, canvas_id: str) -> Tuple[Optional[int], Optional[int]]:
        match = self.TILE_ID_PATTERN.match(canvas_id)
        if not match:
            return None, None
        return int(match.group("x")), int(match.group("y"))

    def _build_canvas_info(self, canvas_element, anchor_rect: Dict = None) -> CanvasInfo:
        if anchor_rect is None:
            anchor_rect = self._get_anchor_rect()
        
        canvas_rect = self._element_rect(canvas_element)
        canvas_id = canvas_element.get_attribute("id") or "unknown"
        tile_x, tile_y = self._parse_tile_id(canvas_id)

        return CanvasInfo(
            id=canvas_id,
            tile=(tile_x, tile_y),
            screen_left=canvas_rect["left"],
            screen_top=canvas_rect["top"],
            width=canvas_rect["width"],
            height=canvas_rect["height"],
            relative_left=canvas_rect["left"] - anchor_rect["left"],
            relative_top=canvas_rect["top"] - anchor_rect["top"],
        )

    def locate(self, canvas_id: str) -> CanvasInfo:
        """Mesure la position d'un canvas spécifique."""
        self._require_driver()
        canvas = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, canvas_id))
        )
        return self._build_canvas_info(canvas)

    def locate_all(self) -> List[CanvasInfo]:
        """Retourne la liste de tous les canvas présents sous #anchor (cached)."""
        self._require_driver()
        if self._descriptors_cache is None:
            anchor_rect = self._get_anchor_rect()
            canvases = self.driver.find_elements(
                By.CSS_SELECTOR, f"{self.anchor_selector} {self.canvas_selector}"
            )
            self._descriptors_cache = [
                self._build_canvas_info(canvas, anchor_rect) for canvas in canvases
            ]
        return self._descriptors_cache

    def find_canvas_for_point(self, relative_x: float, relative_y: float) -> Optional[CanvasInfo]:
        """Retourne le canvas qui recouvre une coordonnée dans le CanvasSpace."""
        for info in self.locate_all():
            if (
                info.relative_left <= relative_x < info.relative_left + info.width
                and info.relative_top <= relative_y < info.relative_top + info.height
            ):
                return info
        return None

    def refresh_cache(self) -> None:
        """Force le rafraîchissement du cache."""
        self._anchor_rect_cache = None
        self._descriptors_cache = None
