"""
Frontier - Extraction de frontières et intégration TensorGrid (S2.3)

Extrait les frontières pour S4 Solver et coordonne avec S6 Pathfinder:
- Calcul de frontier_mask pour TensorGrid
- Identification des cellules de frontière critiques
- Intégration avec les résultats de matching S2
- Publication d'indices vers S6 via HintCache
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
import time
import threading

from .s22_matching import MatchingResult, BatchMatchingResult
from ..s3_tensor.tensor_grid import TensorGrid, CellSymbol, GridBounds
from ..s3_tensor.hint_cache import HintCache, HintType


class FrontierType(Enum):
    """Types de cellules de frontière"""
    ADJACENT_TO_NUMBERS = "adjacent_to_numbers"  # Adjacentes à des nombres révélés
    EDGE_OF_KNOWN_REGION = "edge_of_known_region"  # Bordure des régions connues
    HIGH_PRIORITY = "high_priority"               # Haute priorité pour solver
    EXPANSION_CANDIDATE = "expansion_candidate"   # Candidates à l'expansion


@dataclass
class FrontierCell:
    """Cellule de frontière avec métadonnées"""
    grid_coordinates: Tuple[int, int]
    frontier_type: FrontierType
    priority: float  # 0.0..1.0
    neighbor_count: int  # Nombre de voisins révélés
    distance_to_center: float
    timestamp: float
    
    def to_tensor_grid_mask(self) -> bool:
        """Convertit en valeur pour frontier_mask"""
        return True  # Toutes les cellules de frontière sont marquées
    
    def get_hint_data(self) -> Dict[str, Any]:
        """Retourne les données pour HintCache"""
        return {
            'coordinates': self.grid_coordinates,
            'type': self.frontier_type.value,
            'priority': self.priority,
            'neighbor_count': self.neighbor_count,
            'distance_to_center': self.distance_to_center
        }


@dataclass
class FrontierExtractionResult:
    """Résultat de l'extraction de frontière"""
    success: bool
    frontier_cells: List[FrontierCell]
    frontier_bounds: GridBounds
    frontier_mask: np.ndarray
    extraction_time: float
    metadata: Dict[str, Any]
    
    def get_high_priority_cells(self, threshold: float = 0.7) -> List[FrontierCell]:
        """Retourne les cellules de haute priorité"""
        return [cell for cell in self.frontier_cells if cell.priority >= threshold]
    
    def get_frontier_density_map(self) -> np.ndarray:
        """Retourne une carte de densité de la frontière"""
        if not self.success or len(self.frontier_cells) == 0:
            return np.array([])
        
        # Créer une grille de densité basée sur les positions
        bounds = self.frontier_bounds
        width = bounds.width()
        height = bounds.height()
        
        density_map = np.zeros((height, width), dtype=np.float32)
        
        for cell in self.frontier_cells:
            local_x = cell.grid_coordinates[0] - bounds.x_min
            local_y = cell.grid_coordinates[1] - bounds.y_min
            
            if 0 <= local_x < width and 0 <= local_y < height:
                density_map[local_y, local_x] = cell.priority
        
        return density_map


class FrontierExtractor:
    """
    Extracteur de frontières pour S2 Recognition
    
    Fonctionnalités:
    - Extraction des frontières à partir de TensorGrid
    - Intégration avec les résultats de matching S2
    - Publication d'indices vers S6 Pathfinder
    - Optimisation des performances
    """
    
    def __init__(self, tensor_grid: TensorGrid, hint_cache: HintCache,
                 enable_adaptive_priority: bool = True,
                 frontier_update_threshold: int = 5):
        """
        Initialise l'extracteur de frontières
        
        Args:
            tensor_grid: Grille tensorielle S3
            hint_cache: Cache d'indices S3
            enable_adaptive_priority: Activer les priorités adaptatives
            frontier_update_threshold: Seuil de mises à jour pour recalcul
        """
        # Dépendances
        self.tensor_grid = tensor_grid
        self.hint_cache = hint_cache
        
        # Configuration
        self.enable_adaptive_priority = enable_adaptive_priority
        self.frontier_update_threshold = frontier_update_threshold
        
        # État et cache
        self._lock = threading.RLock()
        self._last_extraction: Optional[FrontierExtractionResult] = None
        self._extraction_counter: int = 0
        self._priority_weights: Dict[str, float] = {
            'neighbor_weight': 0.4,
            'distance_weight': 0.3,
            'center_weight': 0.3
        }
        
        # Statistiques
        self._stats = {
            'extractions_performed': 0,
            'total_frontier_cells': 0,
            'high_priority_cells': 0,
            'average_extraction_time': 0.0,
            'hints_published': 0
        }
    
    def extract_frontier(self, viewport_bounds: GridBounds,
                         matching_results: Optional[List[MatchingResult]] = None) -> FrontierExtractionResult:
        """
        Extrait les frontières pour une région viewport
        
        Args:
            viewport_bounds: Bornes du viewport actuel
            matching_results: Résultats de matching S2 (optionnel)
            
        Returns:
            Résultat de l'extraction de frontière
        """
        start_time = time.time()
        
        try:
            # Extraire la région de TensorGrid
            grid_region = self.tensor_grid.get_region(viewport_bounds)
            symbols = grid_region['symbols']
            confidence = grid_region['confidence']
            
            # Identifier les cellules révélées (nombres)
            revealed_mask = self._get_revealed_cells_mask(symbols)
            
            # Calculer la frontière
            frontier_mask = self._compute_frontier_mask(symbols, revealed_mask)
            
            # Extraire les cellules de frontière
            frontier_cells = self._extract_frontier_cells(
                frontier_mask, viewport_bounds, matching_results
            )
            
            # Calculer les bornes de la frontière
            frontier_bounds = self._calculate_frontier_bounds(frontier_cells, viewport_bounds)
            
            # Publier les indices vers S6
            self._publish_frontier_hints(frontier_cells, viewport_bounds)
            
            # Mettre à jour TensorGrid avec frontier_mask
            self._update_tensor_grid_frontier(viewport_bounds, frontier_mask)
            
            # Créer le résultat
            extraction_time = time.time() - start_time
            result = FrontierExtractionResult(
                success=True,
                frontier_cells=frontier_cells,
                frontier_bounds=frontier_bounds,
                frontier_mask=frontier_mask,
                extraction_time=extraction_time,
                metadata={
                    'viewport_bounds': viewport_bounds,
                    'revealed_cells_count': int(np.sum(revealed_mask)),
                    'frontier_cells_count': len(frontier_cells),
                    'extraction_id': self._extraction_counter
                }
            )
            
            # Mettre à jour les statistiques
            self._update_stats(len(frontier_cells), extraction_time)
            self._extraction_counter += 1
            
            # Mettre en cache
            self._last_extraction = result
            
            return result
            
        except Exception as e:
            return FrontierExtractionResult(
                success=False,
                frontier_cells=[],
                frontier_bounds=viewport_bounds,
                frontier_mask=np.array([]),
                extraction_time=time.time() - start_time,
                metadata={'error': str(e)}
            )
    
    def should_update_frontier(self, viewport_bounds: GridBounds) -> bool:
        """
        Détermine si la frontière doit être mise à jour
        
        Args:
            viewport_bounds: Bornes du viewport actuel
            
        Returns:
            True si une mise à jour est nécessaire
        """
        # Vérifier si nous avons un résultat précédent
        if self._last_extraction is None:
            return True
        
        # Vérifier si le viewport a changé significativement
        last_bounds = self._last_extraction.frontier_bounds
        bounds_changed = (
            abs(viewport_bounds.x_min - last_bounds.x_min) > self.frontier_update_threshold or
            abs(viewport_bounds.y_min - last_bounds.y_min) > self.frontier_update_threshold
        )
        
        if bounds_changed:
            return True
        
        # Vérifier si TensorGrid a été mis à jour
        dirty_regions = self.tensor_grid.get_dirty_regions(
            since=self._last_extraction.metadata.get('timestamp', 0)
        )
        
        return len(dirty_regions) > 0
    
    def get_frontier_for_solver(self) -> List[Tuple[int, int]]:
        """
        Retourne les coordonnées de frontière pour S4 Solver
        
        Returns:
            Liste des coordonnées (x, y) des cellules de frontière
        """
        if self._last_extraction is None or not self._last_extraction.success:
            return []
        
        # Retourner les cellules de haute priorité d'abord
        high_priority = self._last_extraction.get_high_priority_cells(0.5)
        
        return [cell.grid_coordinates for cell in high_priority]
    
    def get_frontier_density_for_pathfinder(self) -> Optional[np.ndarray]:
        """
        Retourne la carte de densité pour S6 Pathfinder
        
        Returns:
            Carte de densité ou None si pas de frontière
        """
        if self._last_extraction is None or not self._last_extraction.success:
            return None
        
        return self._last_extraction.get_frontier_density_map()
    
    def _get_revealed_cells_mask(self, symbols: np.ndarray) -> np.ndarray:
        """Identifie les cellules révélées (nombres)"""
        # Les cellules révélées sont les nombres 1-8
        revealed_mask = np.zeros_like(symbols, dtype=bool)
        
        for i in range(1, 9):
            revealed_mask |= (symbols == i)
        
        return revealed_mask
    
    def _compute_frontier_mask(self, symbols: np.ndarray, 
                              revealed_mask: np.ndarray) -> np.ndarray:
        """Calcule le masque de frontière"""
        height, width = symbols.shape
        frontier_mask = np.zeros_like(symbols, dtype=bool)
        
        # Pour chaque cellule non-révélée, vérifier si elle est adjacente à une révélée
        for y in range(height):
            for x in range(width):
                if not revealed_mask[y, x] and symbols[y, x] != CellSymbol.FLAGGED.value:
                    # Vérifier les 8 voisins
                    has_revealed_neighbor = False
                    
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            
                            ny, nx = y + dy, x + dx
                            
                            if (0 <= ny < height and 0 <= nx < width and 
                                revealed_mask[ny, nx]):
                                has_revealed_neighbor = True
                                break
                        
                        if has_revealed_neighbor:
                            break
                    
                    if has_revealed_neighbor:
                        frontier_mask[y, x] = True
        
        return frontier_mask
    
    def _extract_frontier_cells(self, frontier_mask: np.ndarray,
                               viewport_bounds: GridBounds,
                               matching_results: Optional[List[MatchingResult]] = None) -> List[FrontierCell]:
        """Extrait les cellules de frontière avec métadonnées"""
        frontier_cells = []
        height, width = frontier_mask.shape
        
        # Créer un mapping des résultats de matching
        matching_map = {}
        if matching_results:
            matching_map = {
                result.grid_coordinates: result
                for result in matching_results
            }
        
        # Calculer le centre du viewport
        center_x = (viewport_bounds.x_min + viewport_bounds.x_max) // 2
        center_y = (viewport_bounds.y_min + viewport_bounds.y_max) // 2
        
        for y in range(height):
            for x in range(width):
                if frontier_mask[y, x]:
                    # Coordonnées grille globales
                    grid_x = viewport_bounds.x_min + x
                    grid_y = viewport_bounds.y_min + y
                    
                    # Compter les voisins révélés
                    neighbor_count = self._count_revealed_neighbors(
                        x, y, frontier_mask, viewport_bounds
                    )
                    
                    # Calculer la distance au centre
                    distance_to_center = np.sqrt(
                        (grid_x - center_x) ** 2 + (grid_y - center_y) ** 2
                    )
                    
                    # Calculer la priorité
                    priority = self._calculate_frontier_priority(
                        neighbor_count, distance_to_center, matching_map.get((grid_x, grid_y))
                    )
                    
                    # Déterminer le type de frontière
                    frontier_type = self._determine_frontier_type(
                        neighbor_count, priority, distance_to_center
                    )
                    
                    cell = FrontierCell(
                        grid_coordinates=(grid_x, grid_y),
                        frontier_type=frontier_type,
                        priority=priority,
                        neighbor_count=neighbor_count,
                        distance_to_center=distance_to_center,
                        timestamp=time.time()
                    )
                    
                    frontier_cells.append(cell)
        
        return frontier_cells
    
    def _count_revealed_neighbors(self, x: int, y: int, frontier_mask: np.ndarray,
                                  viewport_bounds: GridBounds) -> int:
        """Compte les voisins révélés d'une cellule"""
        # Extraire la région de TensorGrid pour compter les voisins révélés
        grid_region = self.tensor_grid.get_region(viewport_bounds)
        symbols = grid_region['symbols']
        
        height, width = symbols.shape
        count = 0
        
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                ny, nx = y + dy, x + dx
                
                if (0 <= ny < height and 0 <= nx < width):
                    symbol = symbols[ny, nx]
                    if 1 <= symbol <= 8:  # Nombre révélé
                        count += 1
        
        return count
    
    def _calculate_frontier_priority(self, neighbor_count: int, distance_to_center: float,
                                    matching_result: Optional[MatchingResult] = None) -> float:
        """Calcule la priorité d'une cellule de frontière"""
        # Priorité basée sur le nombre de voisins
        neighbor_priority = min(1.0, neighbor_count / 8.0)
        
        # Priorité basée sur la distance (plus proche = plus prioritaire)
        max_distance = 50.0  # Distance maximale attendue
        distance_priority = max(0.0, 1.0 - distance_to_center / max_distance)
        
        # Priorité basée sur le résultat de matching
        matching_priority = 0.5  # Valeur par défaut
        if matching_result:
            # Utiliser la confiance du matching
            matching_priority = matching_result.final_confidence
        
        # Combiner les priorités
        combined_priority = (
            neighbor_priority * self._priority_weights['neighbor_weight'] +
            distance_priority * self._priority_weights['distance_weight'] +
            matching_priority * self._priority_weights['center_weight']
        )
        
        return np.clip(combined_priority, 0.0, 1.0)
    
    def _determine_frontier_type(self, neighbor_count: int, priority: float,
                                 distance_to_center: float) -> FrontierType:
        """Détermine le type de frontière d'une cellule"""
        if priority >= 0.8:
            return FrontierType.HIGH_PRIORITY
        elif neighbor_count >= 3:
            return FrontierType.ADJACENT_TO_NUMBERS
        elif distance_to_center < 10:
            return FrontierType.EDGE_OF_KNOWN_REGION
        else:
            return FrontierType.EXPANSION_CANDIDATE
    
    def _calculate_frontier_bounds(self, frontier_cells: List[FrontierCell],
                                   viewport_bounds: GridBounds) -> GridBounds:
        """Calcule les bornes de la région de frontière"""
        if not frontier_cells:
            return viewport_bounds
        
        x_coords = [cell.grid_coordinates[0] for cell in frontier_cells]
        y_coords = [cell.grid_coordinates[1] for cell in frontier_cells]
        
        return GridBounds(
            x_min=min(x_coords),
            y_min=min(y_coords),
            x_max=max(x_coords),
            y_max=max(y_coords)
        )
    
    def _publish_frontier_hints(self, frontier_cells: List[FrontierCell],
                               viewport_bounds: GridBounds) -> None:
        """Publie les indices de frontière vers S6 Pathfinder"""
        try:
            # Créer les données d'indices
            hint_data = {
                'frontier_bounds': {
                    'x_min': viewport_bounds.x_min,
                    'y_min': viewport_bounds.y_min,
                    'x_max': viewport_bounds.x_max,
                    'y_max': viewport_bounds.y_max
                },
                'frontier_cells': [cell.get_hint_data() for cell in frontier_cells],
                'high_priority_count': len([c for c in frontier_cells if c.priority >= 0.7]),
                'total_count': len(frontier_cells),
                'timestamp': time.time()
            }
            
            # Publier via HintCache
            self.hint_cache.publish_hint(
                hint_type=HintType.FRONTIER_UPDATE,
                data=hint_data,
                priority=0.8
            )
            
            self._stats['hints_published'] += 1
            
        except Exception:
            # Ignorer les erreurs de publication
            pass
    
    def _update_tensor_grid_frontier(self, viewport_bounds: GridBounds,
                                    frontier_mask: np.ndarray) -> None:
        """Met à jour TensorGrid avec le masque de frontière"""
        try:
            self.tensor_grid.update_region(
                bounds=viewport_bounds,
                frontier_mask=frontier_mask
            )
        except Exception:
            # Ignorer les erreurs de mise à jour
            pass
    
    def _update_stats(self, frontier_count: int, extraction_time: float) -> None:
        """Met à jour les statistiques"""
        with self._lock:
            self._stats['extractions_performed'] += 1
            self._stats['total_frontier_cells'] += frontier_count
            
            # Mettre à jour le temps moyen
            total_extractions = self._stats['extractions_performed']
            current_avg = self._stats['average_extraction_time']
            self._stats['average_extraction_time'] = (
                (current_avg * (total_extractions - 1) + extraction_time) / total_extractions
            )
            
            # Compter les cellules de haute priorité
            if self._last_extraction:
                high_priority = len(self._last_extraction.get_high_priority_cells())
                self._stats['high_priority_cells'] += high_priority
    
    def update_priority_weights(self, weights: Dict[str, float]) -> None:
        """
        Met à jour les poids de priorité
        
        Args:
            weights: Nouveaux poids (neighbor_weight, distance_weight, center_weight)
        """
        if self.enable_adaptive_priority:
            total = sum(weights.values())
            if total > 0:
                # Normaliser les poids
                self._priority_weights = {
                    key: value / total for key, value in weights.items()
                }
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de l'extracteur"""
        with self._lock:
            stats = self._stats.copy()
            stats.update({
                'extraction_counter': self._extraction_counter,
                'has_cached_result': self._last_extraction is not None,
                'priority_weights': self._priority_weights.copy(),
                'configuration': {
                    'adaptive_priority': self.enable_adaptive_priority,
                    'update_threshold': self.frontier_update_threshold
                }
            })
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'extractions_performed': 0,
                'total_frontier_cells': 0,
                'high_priority_cells': 0,
                'average_extraction_time': 0.0,
                'hints_published': 0
            }
    
    def clear_cache(self) -> None:
        """Efface le cache d'extraction"""
        with self._lock:
            self._last_extraction = None
