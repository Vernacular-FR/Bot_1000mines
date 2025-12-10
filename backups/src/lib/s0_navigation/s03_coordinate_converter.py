"""
CoordinateConverter - Conversion de coordonnées grille ↔ écran (S0.3)

Gère les transformations entre les différents systèmes de coordonnées:
- Grid coordinates: indices logiques des cellules (x, y)
- Canvas coordinates: pixels relatifs au canvas du jeu
- Screen coordinates: pixels absolus sur l'écran
- Viewport coordinates: pixels visibles dans le viewport actuel
"""

import math
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
import time

from ..s3_tensor.tensor_grid import GridBounds


@dataclass
class Point2D:
    """Point 2D générique"""
    x: float
    y: float
    
    def distance_to(self, other: 'Point2D') -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


class CoordinateConverter:
    """
    Convertisseur de coordonnées pour l'interaction avec le jeu
    
    Fonctionnalités:
    - Conversion Grid ↔ Canvas ↔ Screen
    - Gestion du viewport et des offsets
    - Calibration dynamique des tailles de cellules
    - Support pour les différentes résolutions d'écran
    """
    
    def __init__(self, cell_size: int = 24, cell_border: int = 1):
        """
        Initialise le convertisseur de coordonnées
        
        Args:
            cell_size: Taille d'une cellule en pixels (intérieur)
            cell_border: Épaisseur des bordures en pixels
        """
        # Configuration des cellules
        self.cell_size = cell_size
        self.cell_border = cell_border
        self.cell_total = cell_size + cell_border  # Taille totale incluant bordure
        self.cell_center_offset = self.cell_total // 2
        
        # Offsets et ancrage
        self.anchor_offset: Point2D = Point2D(0, 0)  # Offset du canvas #anchor
        self.viewport_offset: Point2D = Point2D(0, 0)  # Offset du viewport actuel
        self.screen_offset: Point2D = Point2D(0, 0)  # Offset de l'écran
        
        # Calibration dynamique
        self._calibrated_cell_size: Optional[int] = None
        self._calibration_timestamp: float = 0.0
        self._calibration_validity: float = 300.0  # 5 minutes
        
        # Cache des conversions
        self._conversion_cache: Dict[str, Tuple[float, float]] = {}
        self._cache_max_size: int = 1000
    
    def set_anchor_offset(self, x: int, y: int) -> None:
        """
        Définit l'offset de l'élément anchor du jeu
        
        Args:
            x, y: Position de l'anchor en coordonnées écran
        """
        self.anchor_offset = Point2D(x, y)
        self._invalidate_cache()
    
    def set_viewport_offset(self, x: int, y: int) -> None:
        """
        Définit l'offset du viewport actuel
        
        Args:
            x, y: Position du viewport en coordonnées canvas
        """
        self.viewport_offset = Point2D(x, y)
        self._invalidate_cache()
    
    def calibrate_cell_size(self, measured_size: int) -> None:
        """
        Calibre dynamiquement la taille des cellules
        
        Args:
            measured_size: Taille mesurée d'une cellule en pixels
        """
        if measured_size > 10 and measured_size < 50:  # Validation raisonnable
            self._calibrated_cell_size = measured_size
            self.cell_total = measured_size
            self.cell_center_offset = measured_size // 2
            self._calibration_timestamp = time.time()
            self._invalidate_cache()
    
    def grid_to_canvas(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """
        Convertit les coordonnées de grille en coordonnées canvas
        
        Args:
            grid_x, grid_y: Coordonnées dans la grille (indices de cellules)
            
        Returns:
            Coordonnées canvas en pixels
        """
        cache_key = f"g2c_{grid_x}_{grid_y}"
        
        if cache_key in self._conversion_cache:
            return self._conversion_cache[cache_key]
        
        # Conversion: grid → canvas
        canvas_x = grid_x * self.cell_total + self.cell_center_offset
        canvas_y = grid_y * self.cell_total + self.cell_center_offset
        
        result = (canvas_x, canvas_y)
        
        # Mettre en cache
        self._cache_conversion(cache_key, result)
        
        return result
    
    def canvas_to_grid(self, canvas_x: float, canvas_y: float) -> Tuple[int, int]:
        """
        Convertit les coordonnées canvas en coordonnées de grille
        
        Args:
            canvas_x, canvas_y: Coordonnées canvas en pixels
            
        Returns:
            Coordonnées grille (indices de cellules)
        """
        cache_key = f"c2g_{int(canvas_x)}_{int(canvas_y)}"
        
        if cache_key in self._conversion_cache:
            return self._conversion_cache[cache_key]
        
        # Conversion: canvas → grid
        grid_x = int((canvas_x - self.cell_center_offset) / self.cell_total)
        grid_y = int((canvas_y - self.cell_center_offset) / self.cell_total)
        
        # Correction pour les valeurs négatives
        if canvas_x < self.cell_center_offset:
            grid_x = -1
        if canvas_y < self.cell_center_offset:
            grid_y = -1
        
        result = (grid_x, grid_y)
        
        # Mettre en cache
        self._cache_conversion(cache_key, result)
        
        return result
    
    def canvas_to_screen(self, canvas_x: float, canvas_y: float) -> Tuple[float, float]:
        """
        Convertit les coordonnées canvas en coordonnées écran
        
        Args:
            canvas_x, canvas_y: Coordonnées canvas en pixels
            
        Returns:
            Coordonnées écran absolues en pixels
        """
        screen_x = canvas_x + self.anchor_offset.x
        screen_y = canvas_y + self.anchor_offset.y
        
        return (screen_x, screen_y)
    
    def screen_to_canvas(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        """
        Convertit les coordonnées écran en coordonnées canvas
        
        Args:
            screen_x, screen_y: Coordonnées écran absolues
            
        Returns:
            Coordonnées canvas en pixels
        """
        canvas_x = screen_x - self.anchor_offset.x
        canvas_y = screen_y - self.anchor_offset.y
        
        return (canvas_x, canvas_y)
    
    def grid_to_screen(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """
        Convertit directement les coordonnées grille en coordonnées écran
        
        Args:
            grid_x, grid_y: Coordonnées grille
            
        Returns:
            Coordonnées écran absolues
        """
        canvas_x, canvas_y = self.grid_to_canvas(grid_x, grid_y)
        return self.canvas_to_screen(canvas_x, canvas_y)
    
    def screen_to_grid(self, screen_x: float, screen_y: float) -> Tuple[int, int]:
        """
        Convertit directement les coordonnées écran en coordonnées grille
        
        Args:
            screen_x, screen_y: Coordonnées écran absolues
            
        Returns:
            Coordonnées grille
        """
        canvas_x, canvas_y = self.screen_to_canvas(screen_x, screen_y)
        return self.canvas_to_grid(canvas_x, canvas_y)
    
    def grid_bounds_to_canvas(self, bounds: GridBounds) -> GridBounds:
        """
        Convertit les bornes de grille en bornes canvas
        
        Args:
            bounds: Bornes en coordonnées grille
            
        Returns:
            Bornes en coordonnées canvas
        """
        top_left = self.grid_to_canvas(bounds.x_min, bounds.y_min)
        bottom_right = self.grid_to_canvas(bounds.x_max, bounds.y_max)
        
        # Ajouter une marge pour inclure les bordures complètes
        margin = self.cell_border // 2
        
        return GridBounds(
            x_min=int(top_left[0] - margin),
            y_min=int(top_left[1] - margin),
            x_max=int(bottom_right[0] + margin),
            y_max=int(bottom_right[1] + margin)
        )
    
    def canvas_bounds_to_grid(self, bounds: GridBounds) -> GridBounds:
        """
        Convertit les bornes canvas en bornes de grille
        
        Args:
            bounds: Bornes en coordonnées canvas
            
        Returns:
            Bornes en coordonnées grille
        """
        top_left = self.canvas_to_grid(bounds.x_min, bounds.y_min)
        bottom_right = self.canvas_to_grid(bounds.x_max, bounds.y_max)
        
        return GridBounds(
            x_min=top_left[0],
            y_min=top_left[1],
            x_max=bottom_right[0],
            y_max=bottom_right[1]
        )
    
    def get_cell_center(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """
        Retourne le centre d'une cellule en coordonnées canvas
        
        Args:
            grid_x, grid_y: Coordonnées de la cellule
            
        Returns:
            Centre de la cellule en coordonnées canvas
        """
        return self.grid_to_canvas(grid_x, grid_y)
    
    def get_cell_bounds(self, grid_x: int, grid_y: int) -> GridBounds:
        """
        Retourne les bornes d'une cellule en coordonnées canvas
        
        Args:
            grid_x, grid_y: Coordonnées de la cellule
            
        Returns:
            Bornes de la cellule en coordonnées canvas
        """
        canvas_x, canvas_y = self.grid_to_canvas(grid_x, grid_y)
        
        half_cell = self.cell_size // 2
        
        return GridBounds(
            x_min=int(canvas_x - half_cell),
            y_min=int(canvas_y - half_cell),
            x_max=int(canvas_x + half_cell),
            y_max=int(canvas_y + half_cell)
        )
    
    def is_valid_grid_position(self, grid_x: int, grid_y: int) -> bool:
        """
        Vérifie si une position grille est valide
        
        Args:
            grid_x, grid_y: Coordonnées à vérifier
            
        Returns:
            True si la position est valide
        """
        return grid_x >= 0 and grid_y >= 0
    
    def get_viewport_grid_bounds(self, viewport_width: int, viewport_height: int) -> GridBounds:
        """
        Calcule les bornes grille visibles dans le viewport actuel
        
        Args:
            viewport_width: Largeur du viewport en pixels
            viewport_height: Hauteur du viewport en pixels
            
        Returns:
            Bornes grille visibles
        """
        # Convertir les coins du viewport en coordonnées grille
        top_left = self.canvas_to_grid(
            self.viewport_offset.x, 
            self.viewport_offset.y
        )
        bottom_right = self.canvas_to_grid(
            self.viewport_offset.x + viewport_width,
            self.viewport_offset.y + viewport_height
        )
        
        return GridBounds(
            x_min=max(0, top_left[0]),
            y_min=max(0, top_left[1]),
            x_max=bottom_right[0],
            y_max=bottom_right[1]
        )
    
    def _cache_conversion(self, key: str, value: Tuple[float, float]) -> None:
        """Met en cache une conversion"""
        if len(self._conversion_cache) >= self._cache_max_size:
            # Vider le cache à moitié
            keys_to_remove = list(self._conversion_cache.keys())[:self._cache_max_size // 2]
            for k in keys_to_remove:
                del self._conversion_cache[k]
        
        self._conversion_cache[key] = value
    
    def _invalidate_cache(self) -> None:
        """Invalide le cache de conversions"""
        self._conversion_cache.clear()
    
    def is_calibration_valid(self) -> bool:
        """Vérifie si la calibration est encore valide"""
        return (self._calibrated_cell_size is not None and
                time.time() - self._calibration_timestamp < self._calibration_validity)
    
    def get_effective_cell_size(self) -> int:
        """Retourne la taille effective des cellules (calibrée si disponible)"""
        if self.is_calibration_valid():
            return self._calibrated_cell_size
        return self.cell_size
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du convertisseur"""
        return {
            'cell_size': self.cell_size,
            'cell_border': self.cell_border,
            'effective_cell_size': self.get_effective_cell_size(),
            'anchor_offset': (self.anchor_offset.x, self.anchor_offset.y),
            'viewport_offset': (self.viewport_offset.x, self.viewport_offset.y),
            'cache_size': len(self._conversion_cache),
            'calibration_valid': self.is_calibration_valid(),
            'calibration_age': time.time() - self._calibration_timestamp if self._calibrated_cell_size else 0.0
        }
    
    def reset_calibration(self) -> None:
        """Réinitialise la calibration"""
        self._calibrated_cell_size = None
        self._calibration_timestamp = 0.0
        self._invalidate_cache()
    
    def debug_conversion(self, grid_x: int, grid_y: int) -> Dict[str, Any]:
        """
        Débogue une conversion complète pour une position grille
        
        Args:
            grid_x, grid_y: Coordonnées grille à déboguer
            
        Returns:
            Informations détaillées sur la conversion
        """
        canvas_coords = self.grid_to_canvas(grid_x, grid_y)
        screen_coords = self.canvas_to_screen(*canvas_coords)
        cell_bounds = self.get_cell_bounds(grid_x, grid_y)
        
        return {
            'grid_coords': (grid_x, grid_y),
            'canvas_coords': canvas_coords,
            'screen_coords': screen_coords,
            'cell_bounds_canvas': {
                'x_min': cell_bounds.x_min,
                'y_min': cell_bounds.y_min,
                'x_max': cell_bounds.x_max,
                'y_max': cell_bounds.y_max
            },
            'cell_size': self.get_effective_cell_size(),
            'anchor_offset': (self.anchor_offset.x, self.anchor_offset.y)
        }
