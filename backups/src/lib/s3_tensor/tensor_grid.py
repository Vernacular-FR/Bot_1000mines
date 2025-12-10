"""
TensorGrid - Grille tensorielle partagée pour l'état du jeu (S3)

Stockage centralisé de l'état du jeu avec optimisations mémoire:
- Grille multi-tenseur (symboles, confiance, âge, frontière)
- Vues optimisées pour solver et analyse
- Mise à jour par régions avec dirty tracking
- Interface thread-safe pour accès concurrent
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time
import threading


class CellSymbol(Enum):
    """Symboles des cellules dans la grille tensorielle"""
    UNKNOWN = -1
    UNREVEALED = -2
    EMPTY = 0
    MINE = 9
    FLAGGED = 10
    NUMBER_1 = 1
    NUMBER_2 = 2
    NUMBER_3 = 3
    NUMBER_4 = 4
    NUMBER_5 = 5
    NUMBER_6 = 6
    NUMBER_7 = 7
    NUMBER_8 = 8


@dataclass
class GridBounds:
    """Bornes d'une région dans la grille"""
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    
    def width(self) -> int:
        return self.x_max - self.x_min + 1
    
    def height(self) -> int:
        return self.y_max - self.y_min + 1
    
    def area(self) -> int:
        return self.width() * self.height()
    
    def contains(self, x: int, y: int) -> bool:
        return (self.x_min <= x <= self.x_max and 
                self.y_min <= y <= self.y_max)
    
    def intersects(self, other: 'GridBounds') -> bool:
        return not (self.x_max < other.x_min or self.x_min > other.x_max or
                   self.y_max < other.y_min or self.y_min > other.y_max)


@dataclass
class DirtyRegion:
    """Région marquée comme modifiée"""
    bounds: GridBounds
    timestamp: float
    change_type: str  # 'symbols', 'confidence', 'frontier', 'all'
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TensorGrid:
    """
    Grille tensorielle partagée pour l'état du jeu
    
    Fonctionnalités:
    - Stockage multi-tenseur (symboles, confiance, âge, frontière)
    - Vues optimisées pour différents composants
    - Mise à jour par régions avec dirty tracking
    - Thread-safe pour accès concurrent
    """
    
    def __init__(self, initial_bounds: Optional[GridBounds] = None):
        """
        Initialise la grille tensorielle
        
        Args:
            initial_bounds: Bornes initiales (None = grille vide extensible)
        """
        self._lock = threading.RLock()
        
        if initial_bounds is None:
            # Grille vide qui s'étendra dynamiquement
            self._symbols = np.array([], dtype=np.int8).reshape(0, 0)
            self._confidence = np.array([], dtype=np.float32).reshape(0, 0)
            self._age = np.array([], dtype=np.uint64).reshape(0, 0)
            self._frontier_mask = np.array([], dtype=bool).reshape(0, 0)
            self._global_offset = (0, 0)
        else:
            # Grille pré-dimensionnée
            height = initial_bounds.height()
            width = initial_bounds.width()
            self._symbols = np.full((height, width), CellSymbol.UNKNOWN.value, dtype=np.int8)
            self._confidence = np.zeros((height, width), dtype=np.float32)
            self._age = np.zeros((height, width), dtype=np.uint64)
            self._frontier_mask = np.zeros((height, width), dtype=bool)
            self._global_offset = (initial_bounds.x_min, initial_bounds.y_min)
        
        # Suivi des régions modifiées
        self._dirty_regions: List[DirtyRegion] = []
        self._last_update_time = time.time()
        
        # Cache des vues
        self._solver_view_cache: Optional[Dict[str, np.ndarray]] = None
        self._cache_valid = False
    
    def get_solver_view(self) -> Dict[str, Any]:
        """
        Retourne la vue optimisée pour le solver
        
        Returns:
            Dictionnaire avec les arrays et métadonnées pour le solver
        """
        with self._lock:
            if not self._cache_valid or self._solver_view_cache is None:
                self._rebuild_solver_view_cache()
            
            return {
                'symbols': self._solver_view_cache['symbols'].copy(),
                'confidence': self._solver_view_cache['confidence'].copy(),
                'frontier_mask': self._solver_view_cache['frontier_mask'].copy(),
                'global_offset': self._global_offset,
                'timestamp': self._last_update_time
            }
    
    def update_region(self, bounds: GridBounds, symbols: Optional[np.ndarray] = None,
                     confidence: Optional[np.ndarray] = None,
                     frontier_mask: Optional[np.ndarray] = None,
                     dirty_mask: Optional[np.ndarray] = None) -> None:
        """
        Met à jour une région de la grille
        
        Args:
            bounds: Bornes de la région à mettre à jour
            symbols: Array des symboles (optionnel)
            confidence: Array des confiances (optionnel)
            frontier_mask: Array du masque de frontière (optionnel)
            dirty_mask: Masque des cellules réellement modifiées (optionnel)
        """
        with self._lock:
            # Étendre la grille si nécessaire
            self._ensure_bounds(bounds)
            
            # Convertir en coordonnées locales
            local_bounds = self._to_local_bounds(bounds)
            
            # Mettre à jour chaque tenseur si fourni
            change_type = []
            
            if symbols is not None:
                self._symbols[local_bounds.y_min:local_bounds.y_max+1,
                             local_bounds.x_min:local_bounds.x_max+1] = symbols
                change_type.append('symbols')
            
            if confidence is not None:
                self._confidence[local_bounds.y_min:local_bounds.y_max+1,
                                 local_bounds.x_min:local_bounds.x_max+1] = confidence
                change_type.append('confidence')
            
            if frontier_mask is not None:
                self._frontier_mask[local_bounds.y_min:local_bounds.y_max+1,
                                   local_bounds.x_min:local_bounds.x_max+1] = frontier_mask
                change_type.append('frontier')
            
            # Mettre à jour l'âge des cellules modifiées
            current_time = time.time()
            if dirty_mask is not None:
                age_update = np.full_like(dirty_mask, current_time, dtype=np.uint64)
                self._age[local_bounds.y_min:local_bounds.y_max+1,
                         local_bounds.x_min:local_bounds.x_max+1] = np.where(
                    dirty_mask, age_update, self._age[local_bounds.y_min:local_bounds.y_max+1,
                                                     local_bounds.x_min:local_bounds.x_max+1]
                )
            else:
                # Mettre à jour toute la région
                self._age[local_bounds.y_min:local_bounds.y_max+1,
                         local_bounds.x_min:local_bounds.x_max+1] = current_time
            
            # Ajouter la région modifiée
            dirty_region = DirtyRegion(
                bounds=bounds,
                timestamp=current_time,
                change_type=','.join(change_type) if change_type else 'unknown'
            )
            self._dirty_regions.append(dirty_region)
            
            # Invalider le cache
            self._cache_valid = False
            self._last_update_time = current_time
    
    def get_region(self, bounds: GridBounds) -> Dict[str, np.ndarray]:
        """
        Extrait une région spécifique de la grille
        
        Args:
            bounds: Bornes de la région à extraire
            
        Returns:
            Dictionnaire avec les arrays de la région
        """
        with self._lock:
            local_bounds = self._to_local_bounds(bounds)
            
            return {
                'symbols': self._symbols[local_bounds.y_min:local_bounds.y_max+1,
                                        local_bounds.x_min:local_bounds.x_max+1].copy(),
                'confidence': self._confidence[local_bounds.y_min:local_bounds.y_max+1,
                                             local_bounds.x_min:local_bounds.x_max+1].copy(),
                'age': self._age[local_bounds.y_min:local_bounds.y_max+1,
                               local_bounds.x_min:local_bounds.x_max+1].copy(),
                'frontier_mask': self._frontier_mask[local_bounds.y_min:local_bounds.y_max+1,
                                                   local_bounds.x_min:local_bounds.x_max+1].copy()
            }
    
    def get_dirty_regions(self, since: Optional[float] = None) -> List[DirtyRegion]:
        """
        Retourne les régions modifiées
        
        Args:
            since: Timestamp minimum (None = toutes)
            
        Returns:
            Liste des régions modifiées
        """
        with self._lock:
            regions = self._dirty_regions
            if since:
                regions = [r for r in regions if r.timestamp >= since]
            return regions.copy()
    
    def clear_dirty_regions(self) -> None:
        """Efface la liste des régions modifiées"""
        with self._lock:
            self._dirty_regions.clear()
    
    def get_bounds(self) -> GridBounds:
        """Retourne les bornes actuelles de la grille"""
        with self._lock:
            height, width = self._symbols.shape
            offset_x, offset_y = self._global_offset
            
            return GridBounds(
                x_min=offset_x,
                y_min=offset_y,
                x_max=offset_x + width - 1,
                y_max=offset_y + height - 1
            )
    
    def get_cell(self, x: int, y: int) -> Dict[str, Any]:
        """
        Retourne les informations d'une cellule
        
        Args:
            x, y: Coordonnées globales
            
        Returns:
            Dictionnaire avec symbole, confiance, âge, frontière
        """
        with self._lock:
            local_x, local_y = self._to_local_coords(x, y)
            
            if (0 <= local_x < self._symbols.shape[1] and 
                0 <= local_y < self._symbols.shape[0]):
                
                return {
                    'symbol': self._symbols[local_y, local_x],
                    'confidence': self._confidence[local_y, local_x],
                    'age': self._age[local_y, local_x],
                    'is_frontier': self._frontier_mask[local_y, local_x]
                }
            else:
                return {
                    'symbol': CellSymbol.UNKNOWN,
                    'confidence': 0.0,
                    'age': 0,
                    'is_frontier': False
                }
    
    def set_cell(self, x: int, y: int, symbol: CellSymbol, 
                confidence: float = 1.0, is_frontier: bool = False) -> None:
        """
        Définit les informations d'une cellule
        
        Args:
            x, y: Coordonnées globales
            symbol: Symbole de la cellule
            confidence: Confiance (0.0..1.0)
            is_frontier: Si la cellule est en frontière
        """
        bounds = GridBounds(x, y, x, y)
        symbols = np.array([[symbol.value]], dtype=np.int8)
        confidences = np.array([[confidence]], dtype=np.float32)
        frontier = np.array([[is_frontier]], dtype=bool)
        dirty = np.array([[True]], dtype=bool)
        
        self.update_region(bounds, symbols, confidences, frontier, dirty)
    
    def _ensure_bounds(self, bounds: GridBounds) -> None:
        """Étend la grille si nécessaire pour contenir la région spécifiée"""
        current_bounds = self.get_bounds()
        
        # Vérifier si l'extension est nécessaire
        needs_expansion = (
            bounds.x_min < current_bounds.x_min or
            bounds.x_max > current_bounds.x_max or
            bounds.y_min < current_bounds.y_min or
            bounds.y_max > current_bounds.y_max
        )
        
        if not needs_expansion:
            return
        
        # Calculer les nouvelles bornes
        new_x_min = min(current_bounds.x_min, bounds.x_min)
        new_y_min = min(current_bounds.y_min, bounds.y_min)
        new_x_max = max(current_bounds.x_max, bounds.x_max)
        new_y_max = max(current_bounds.y_max, bounds.y_max)
        
        new_bounds = GridBounds(new_x_min, new_y_min, new_x_max, new_y_max)
        
        # Créer les nouveaux tenseurs
        new_height = new_bounds.height()
        new_width = new_bounds.width()
        
        new_symbols = np.full((new_height, new_width), CellSymbol.UNKNOWN.value, dtype=np.int8)
        new_confidence = np.zeros((new_height, new_width), dtype=np.float32)
        new_age = np.zeros((new_height, new_width), dtype=np.uint64)
        new_frontier = np.zeros((new_height, new_width), dtype=bool)
        
        # Calculer les offsets pour copier les anciennes données
        copy_x_offset = current_bounds.x_min - new_x_min
        copy_y_offset = current_bounds.y_min - new_y_min
        
        # Copier les anciennes données
        if self._symbols.size > 0:
            new_symbols[copy_y_offset:copy_y_offset + self._symbols.shape[0],
                       copy_x_offset:copy_x_offset + self._symbols.shape[1]] = self._symbols
            new_confidence[copy_y_offset:copy_y_offset + self._confidence.shape[0],
                          copy_x_offset:copy_x_offset + self._confidence.shape[1]] = self._confidence
            new_age[copy_y_offset:copy_y_offset + self._age.shape[0],
                    copy_x_offset:copy_x_offset + self._age.shape[1]] = self._age
            new_frontier[copy_y_offset:copy_y_offset + self._frontier_mask.shape[0],
                        copy_x_offset:copy_x_offset + self._frontier_mask.shape[1]] = self._frontier_mask
        
        # Remplacer les tenseurs
        self._symbols = new_symbols
        self._confidence = new_confidence
        self._age = new_age
        self._frontier_mask = new_frontier
        self._global_offset = (new_x_min, new_y_min)
        
        # Invalider le cache
        self._cache_valid = False
    
    def _to_local_bounds(self, bounds: GridBounds) -> GridBounds:
        """Convertit les bornes globales en bornes locales"""
        return GridBounds(
            x_min=bounds.x_min - self._global_offset[0],
            y_min=bounds.y_min - self._global_offset[1],
            x_max=bounds.x_max - self._global_offset[0],
            y_max=bounds.y_max - self._global_offset[1]
        )
    
    def _to_local_coords(self, x: int, y: int) -> Tuple[int, int]:
        """Convertit les coordonnées globales en coordonnées locales"""
        return (x - self._global_offset[0], y - self._global_offset[1])
    
    def _rebuild_solver_view_cache(self) -> None:
        """Reconstruit le cache de la vue solver"""
        self._solver_view_cache = {
            'symbols': self._symbols,
            'confidence': self._confidence,
            'frontier_mask': self._frontier_mask
        }
        self._cache_valid = True
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de la grille"""
        with self._lock:
            height, width = self._symbols.shape
            
            return {
                'grid_size': (height, width),
                'total_cells': height * width,
                'unknown_cells': int(np.sum(self._symbols == CellSymbol.UNKNOWN.value)),
                'revealed_cells': int(np.sum((self._symbols >= CellSymbol.EMPTY.value) & 
                                            (self._symbols <= CellSymbol.NUMBER_8.value))),
                'flagged_cells': int(np.sum(self._symbols == CellSymbol.FLAGGED.value)),
                'frontier_cells': int(np.sum(self._frontier_mask)),
                'average_confidence': float(np.mean(self._confidence)),
                'dirty_regions_count': len(self._dirty_regions),
                'last_update_time': self._last_update_time
            }
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques (efface les régions modifiées)"""
        with self._lock:
            self.clear_dirty_regions()
