"""Conversion de coordonnées grille ↔ canvas ↔ écran."""

import math
from typing import Tuple, Optional, Any
from selenium.webdriver.remote.webdriver import WebDriver

from .types import Coord, ScreenPoint, CanvasPoint, GridBounds

# Constantes par défaut (peuvent être overridées via config)
DEFAULT_CELL_SIZE = 24
DEFAULT_CELL_BORDER = 1


class CoordinateConverter:
    """Convertisseur de coordonnées grille/canvas/écran."""

    def __init__(
        self,
        cell_size: int = DEFAULT_CELL_SIZE,
        cell_border: int = DEFAULT_CELL_BORDER,
        driver: WebDriver = None,
    ):
        self.cell_size = cell_size
        self.cell_border = cell_border
        self.cell_total = cell_size + cell_border
        self.cell_center_offset = math.ceil(self.cell_total / 2.0)
        self.driver = driver
        self._anchor_element = None
        self._anchor_cache = None

    def set_driver(self, driver: WebDriver) -> None:
        """Configure le driver et reset le cache."""
        self.driver = driver
        self._anchor_element = None
        self._anchor_cache = None

    def setup_anchor(self) -> None:
        """Configure l'élément anchor comme référence."""
        if not self.driver:
            raise RuntimeError("Driver non initialisé. Utilisez set_driver() d'abord.")
        try:
            self._anchor_element = self.driver.find_element("css selector", "#anchor")
            self._anchor_cache = None
        except Exception as e:
            raise RuntimeError(f"Impossible de trouver l'élément anchor: {e}")

    def _get_anchor_position(self) -> dict:
        """Récupère la position CSS de l'anchor (avec cache)."""
        if not self._anchor_element:
            self.setup_anchor()
        
        if self._anchor_cache is None:
            script = """
            var element = arguments[0];
            var rect = element.getBoundingClientRect();
            return { x: rect.left, y: rect.top };
            """
            self._anchor_cache = self.driver.execute_script(script, self._anchor_element)
        
        return self._anchor_cache

    def refresh_anchor(self) -> None:
        """Force le rafraîchissement du cache anchor."""
        self._anchor_cache = None
        if self._anchor_element:
            self.setup_anchor()

    # === Conversions Canvas ↔ Screen ===

    def canvas_to_screen(self, canvas_x: float, canvas_y: float) -> Tuple[float, float]:
        """Convertit coordonnées canvas → écran."""
        anchor = self._get_anchor_position()
        return (anchor['x'] + canvas_x, anchor['y'] + canvas_y)

    def screen_to_canvas(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        """Convertit coordonnées écran → canvas."""
        anchor = self._get_anchor_position()
        return (screen_x - anchor['x'], screen_y - anchor['y'])

    # === Conversions Grid ↔ Canvas ===

    def grid_to_canvas(self, row: int, col: int) -> Tuple[float, float]:
        """Convertit coordonnées grille → canvas."""
        canvas_x = col * self.cell_total
        canvas_y = row * self.cell_total
        return (canvas_x, canvas_y)

    def canvas_to_grid(self, canvas_x: float, canvas_y: float) -> Tuple[float, float]:
        """Convertit coordonnées canvas → grille (float)."""
        grid_col = canvas_x / self.cell_total
        grid_row = canvas_y / self.cell_total
        return (grid_row, grid_col)

    # === Conversions Grid ↔ Screen ===

    def grid_to_screen(self, row: int, col: int) -> Tuple[float, float]:
        """Convertit coordonnées grille → écran."""
        canvas_x, canvas_y = self.grid_to_canvas(row, col)
        return self.canvas_to_screen(canvas_x, canvas_y)

    def screen_to_grid(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        """Convertit coordonnées écran → grille (float)."""
        canvas_x, canvas_y = self.screen_to_canvas(screen_x, screen_y)
        return self.canvas_to_grid(canvas_x, canvas_y)

    def grid_to_screen_centered(self, row: int, col: int) -> Tuple[float, float]:
        """Retourne les coordonnées écran du centre d'une cellule."""
        screen_x, screen_y = self.grid_to_screen(row, col)
        return (screen_x + self.cell_center_offset, screen_y + self.cell_center_offset)

    # === Helpers Coord/ScreenPoint ===

    def coord_to_screen(self, coord: Coord) -> ScreenPoint:
        """Convertit un Coord en ScreenPoint."""
        x, y = self.grid_to_screen(coord.row, coord.col)
        return ScreenPoint(x=x, y=y)

    def coord_to_screen_centered(self, coord: Coord) -> ScreenPoint:
        """Convertit un Coord en ScreenPoint (centre de la cellule)."""
        x, y = self.grid_to_screen_centered(coord.row, coord.col)
        return ScreenPoint(x=x, y=y)


# === Fonctions standalone (API fonctionnelle) ===

_default_converter: Optional[CoordinateConverter] = None


def _get_converter() -> CoordinateConverter:
    global _default_converter
    if _default_converter is None:
        _default_converter = CoordinateConverter()
    return _default_converter


def set_converter_driver(driver: WebDriver) -> None:
    """Configure le driver pour le convertisseur par défaut."""
    _get_converter().set_driver(driver)


def grid_to_screen(row: int, col: int) -> Tuple[float, float]:
    """Convertit coordonnées grille → écran."""
    return _get_converter().grid_to_screen(row, col)


def screen_to_grid(screen_x: float, screen_y: float) -> Tuple[float, float]:
    """Convertit coordonnées écran → grille."""
    return _get_converter().screen_to_grid(screen_x, screen_y)


def grid_to_screen_centered(row: int, col: int) -> Tuple[float, float]:
    """Retourne les coordonnées écran du centre d'une cellule."""
    return _get_converter().grid_to_screen_centered(row, col)
