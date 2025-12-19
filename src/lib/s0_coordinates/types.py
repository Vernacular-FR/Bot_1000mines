"""Types pour le module s0_coordinates."""

from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any


@dataclass(frozen=True)
class Coord:
    """Coordonnées de grille (row, col)."""
    row: int
    col: int
    
    def __iter__(self):
        return iter((self.row, self.col))
    
    def to_tuple(self) -> Tuple[int, int]:
        return (self.row, self.col)


@dataclass
class ScreenPoint:
    """Point en coordonnées écran (pixels absolus)."""
    x: float
    y: float
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class CanvasPoint:
    """Point en coordonnées canvas (relatif à #anchor)."""
    x: float
    y: float
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class GridBounds:
    """Bornes d'une zone de grille."""
    min_row: int
    min_col: int
    max_row: int
    max_col: int
    
    @property
    def width(self) -> int:
        return self.max_col - self.min_col + 1
    
    @property
    def height(self) -> int:
        return self.max_row - self.min_row + 1
    
    def contains(self, coord: Coord) -> bool:
        return (self.min_row <= coord.row <= self.max_row and 
                self.min_col <= coord.col <= self.max_col)
    
    def to_tuple(self) -> Tuple[int, int, int, int]:
        return (self.min_row, self.min_col, self.max_row, self.max_col)


@dataclass
class CanvasInfo:
    """Informations sur un canvas."""
    id: str
    tile: Tuple[Optional[int], Optional[int]]
    screen_left: float
    screen_top: float
    width: float
    height: float
    relative_left: float
    relative_top: float


@dataclass
class ViewportInfo:
    """Informations sur le viewport."""
    screen_bounds: Tuple[float, float, float, float]  # left, top, right, bottom
    grid_bounds: GridBounds
    dimensions: Tuple[float, float]  # width, height
    position: Tuple[float, float]  # left, top
