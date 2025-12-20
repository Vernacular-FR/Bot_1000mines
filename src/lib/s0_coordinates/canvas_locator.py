"""Localisation des canvas (512×512) autour de #anchor."""

import re
import time
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
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Utiliser JavaScript pour récupérer toutes les infos en un seul appel atomique
                    script = f"""
                    var anchor = document.querySelector("{self.anchor_selector}");
                    if (!anchor) return null;
                    
                    var canvases = anchor.querySelectorAll("{self.canvas_selector}");
                    var results = [];
                    
                    for (var i = 0; i < canvases.length; i++) {{
                        var canvas = canvases[i];
                        var rect = canvas.getBoundingClientRect();
                        var anchorRect = anchor.getBoundingClientRect();
                        
                        results.push({{
                            id: canvas.id,
                            relative_left: rect.left - anchorRect.left,
                            relative_top: rect.top - anchorRect.top,
                            width: rect.width,
                            height: rect.height
                        }});
                    }}
                    
                    return results;
                    """
                    
                    # Exécuter le script JavaScript
                    canvas_data = self.driver.execute_script(script)
                    
                    if canvas_data is None:
                        raise RuntimeError("Anchor element not found")
                    
                    # Convertir les données en CanvasInfo
                    self._descriptors_cache = []
                    for data in canvas_data:
                        # Parser les coordonnées tile depuis l'ID du canvas
                        match = self.TILE_ID_PATTERN.search(data['id'])
                        if match:
                            tile_x = int(match.group('x'))
                            tile_y = int(match.group('y'))
                            tile = (tile_x, tile_y)
                        else:
                            tile = (None, None)
                        
                        # Calculer screen_left/top en utilisant l'anchor
                        anchor_rect = self._get_anchor_rect()
                        screen_left = anchor_rect['left'] + data['relative_left']
                        screen_top = anchor_rect['top'] + data['relative_top']
                        
                        canvas_info = CanvasInfo(
                            id=data['id'],
                            tile=tile,
                            screen_left=screen_left,
                            screen_top=screen_top,
                            width=data['width'],
                            height=data['height'],
                            relative_left=data['relative_left'],
                            relative_top=data['relative_top']
                        )
                        self._descriptors_cache.append(canvas_info)
                    
                    return self._descriptors_cache
                    
                except Exception as e:
                    if "stale element" in str(e).lower() and attempt < max_retries - 1:
                        print(f"[CANVAS] StaleElementReference, retry {attempt + 1}/{max_retries}")
                        # Rafraîchir le cache et réessayer
                        self._anchor_rect_cache = None
                        time.sleep(0.1)  # Petit délai pour laisser le DOM se stabiliser
                        continue
                    else:
                        raise
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
