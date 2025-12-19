"""Gestion du viewport et des zones visibles."""

import math
from typing import List, Tuple, Optional, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver

from .types import Coord, GridBounds, ViewportInfo
from .converter import CoordinateConverter


class ViewportMapper:
    """Lecture des limites du viewport et des zones visibles."""

    def __init__(self, converter: CoordinateConverter, driver: WebDriver = None):
        self.converter = converter
        self.driver = driver
        self._control_element = None

    def set_driver(self, driver: WebDriver) -> None:
        """Configure le driver."""
        self.driver = driver
        self._control_element = None

    def _get_control_element(self):
        """Récupère l'élément #control (viewport graphique)."""
        if not self.driver:
            raise RuntimeError("Driver requis pour ViewportMapper")

        if not self._control_element:
            self._control_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "control"))
            )
        return self._control_element

    def get_viewport_bounds(self) -> Optional[ViewportInfo]:
        """Retourne les informations du viewport."""
        try:
            from src.config import VIEWPORT_CONFIG
            
            control = self._get_control_element()
            width = control.rect['width']
            height = control.rect['height']
            left, top = VIEWPORT_CONFIG['position']
            right = left + width
            bottom = top + height

            # Calcul des bornes grille (cellules entièrement visibles)
            grid_row_top, grid_col_left = self.converter.screen_to_grid(left, top)
            grid_row_bottom, grid_col_right = self.converter.screen_to_grid(right, bottom)

            grid_bounds = GridBounds(
                min_row=math.ceil(grid_row_top),
                min_col=math.ceil(grid_col_left),
                max_row=math.floor(grid_row_bottom) - 1,
                max_col=math.floor(grid_col_right) - 1,
            )

            return ViewportInfo(
                screen_bounds=(left, top, right, bottom),
                grid_bounds=grid_bounds,
                dimensions=(width, height),
                position=(left, top),
            )

        except Exception as e:
            print(f"[ERREUR] Erreur viewport bounds: {e}")
            return None

    def get_visible_grid_bounds(self) -> Optional[GridBounds]:
        """Retourne uniquement les bornes grille visibles."""
        info = self.get_viewport_bounds()
        return info.grid_bounds if info else None

    def get_grid_bounds_for_coords(self, coords: List[Tuple[int, int]]) -> GridBounds:
        """Calcule les bornes d'une liste de coordonnées."""
        if not coords:
            return GridBounds(0, 0, 0, 0)
        
        rows = [c[0] for c in coords]
        cols = [c[1] for c in coords]
        return GridBounds(
            min_row=min(rows),
            min_col=min(cols),
            max_row=max(rows),
            max_col=max(cols),
        )

    def get_screen_bounds_for_grid(self, bounds: GridBounds) -> Tuple[float, float, float, float]:
        """Convertit des bornes grille en bornes écran."""
        top_left = self.converter.grid_to_screen(bounds.min_row, bounds.min_col)
        bottom_right = self.converter.grid_to_screen(bounds.max_row + 1, bounds.max_col + 1)
        return (top_left[0], top_left[1], bottom_right[0], bottom_right[1])

    def get_zone_bounds_contained(
        self, left: float, top: float, right: float, bottom: float
    ) -> Optional[Dict[str, Any]]:
        """Bornes grille/écran d'une zone entièrement contenue."""
        try:
            grid_row_top, grid_col_left = self.converter.screen_to_grid(left, top)
            grid_row_bottom, grid_col_right = self.converter.screen_to_grid(right, bottom)

            grid_bounds = GridBounds(
                min_row=math.ceil(grid_row_top),
                min_col=math.ceil(grid_col_left),
                max_row=math.floor(grid_row_bottom) - 1,
                max_col=math.floor(grid_col_right) - 1,
            )

            return {
                "grid_bounds": grid_bounds,
                "screen_bounds": (left, top, right, bottom),
            }
        except Exception as e:
            print(f"[ERREUR] Zone bounds: {e}")
            return None


# === Fonctions standalone ===

_default_mapper: Optional[ViewportMapper] = None


def _get_mapper() -> ViewportMapper:
    global _default_mapper
    if _default_mapper is None:
        from .converter import CoordinateConverter
        _default_mapper = ViewportMapper(CoordinateConverter())
    return _default_mapper


def set_viewport_driver(driver: WebDriver) -> None:
    """Configure le driver pour le mapper par défaut."""
    mapper = _get_mapper()
    mapper.set_driver(driver)
    mapper.converter.set_driver(driver)


def get_viewport_bounds() -> Optional[ViewportInfo]:
    """Retourne les informations du viewport."""
    return _get_mapper().get_viewport_bounds()


def get_visible_grid_bounds() -> Optional[GridBounds]:
    """Retourne les bornes grille visibles."""
    return _get_mapper().get_visible_grid_bounds()
