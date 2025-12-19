"""Module s0_coordinates : Conversion coordonnées grille ↔ écran."""

from .types import Coord, ScreenPoint, CanvasPoint, GridBounds, CanvasInfo, ViewportInfo
from .converter import CoordinateConverter, grid_to_screen, screen_to_grid, grid_to_screen_centered
from .viewport import ViewportMapper, get_viewport_bounds, get_visible_grid_bounds
from .canvas_locator import CanvasLocator

__all__ = [
    # Types
    "Coord",
    "ScreenPoint", 
    "CanvasPoint",
    "GridBounds",
    "CanvasInfo",
    "ViewportInfo",
    # Converter
    "CoordinateConverter",
    "grid_to_screen",
    "screen_to_grid",
    "grid_to_screen_centered",
    # Viewport
    "ViewportMapper",
    "get_viewport_bounds",
    "get_visible_grid_bounds",
    # Canvas
    "CanvasLocator",
]
