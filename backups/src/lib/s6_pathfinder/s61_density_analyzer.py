"""
DensityAnalyzer - Analyse de densité TensorGrid pour Pathfinder (S6.1)

Calcule les statistiques de densité pour la planification de mouvement:
- Densité des frontières et cellules inconnues
- Analyse de distribution spatiale
- Pondération par criticité et priorité
- Interface directe avec TensorGrid (lecture seule)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time
import threading

# Imports optionnels avec fallbacks
try:
    from scipy import ndimage
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from sklearn.cluster import KMeans
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from ..s3_tensor.tensor_grid import TensorGrid, GridBounds, CellSymbol
from ..s3_tensor.hint_cache import HintCache, HintType


class DensityMetric(Enum):
    """Types de métriques de densité"""
    FRONTIER_DENSITY = "frontier_density"
    UNKNOWN_DENSITY = "unknown_density"
    CRITICAL_DENSITY = "critical_density"
    ACTION_OPPORTUNITY = "action_opportunity"
    COMPLEXITY_SCORE = "complexity_score"


@dataclass
class RegionDensity:
    """Statistiques de densité pour une région"""
    bounds: GridBounds
    total_cells: int
    frontier_cells: int
    unknown_cells: int
    critical_cells: int
    action_opportunities: int
    
    # Densités normalisées (0.0..1.0)
    frontier_density: float
    unknown_density: float
    critical_density: float
    action_density: float
    
    # Métadonnées
    complexity_score: float
    priority_weight: float
    timestamp: float
    
    def get_overall_density(self) -> float:
        """Calcule la densité globale combinée"""
        return (0.4 * self.frontier_density + 
                0.3 * self.unknown_density + 
                0.2 * self.critical_density + 
                0.1 * self.action_density)
    
    def size(self) -> int:
        return self.bounds.width() * self.bounds.height()


@dataclass
class DensityMap:
    """Carte de densité complète pour la grille"""
    global_bounds: GridBounds
    density_grid: np.ndarray  # Grille 2D de densités
    hotspots: List[Tuple[int, int, float]]  # (x, y, density)
    regions: List[RegionDensity]
    global_stats: Dict[str, float]
    
    def get_highest_density_point(self) -> Optional[Tuple[int, int, float]]:
        """Retourne le point de plus haute densité"""
        if not self.hotspots:
            return None
        return max(self.hotspots, key=lambda h: h[2])
    
    def get_top_hotspots(self, count: int = 5) -> List[Tuple[int, int, float]]:
        """Retourne les top N points chauds"""
        return sorted(self.hotspots, key=lambda h: h[2], reverse=True)[:count]


class DensityAnalyzer:
    """
    Analyseur de densité pour le pathfinding
    
    Fonctionnalités:
    - Calcul de densités multi-métriques
    - Identification des zones chaudes
    - Analyse de distribution spatiale
    - Intégration avec les hints du HintCache
    """
    
    def __init__(self, tensor_grid: TensorGrid, hint_cache: HintCache,
                 analysis_window_size: Tuple[int, int] = (10, 10),
                 hotspot_threshold: float = 0.7,
                 enable_clustering: bool = True):
        """
        Initialise l'analyseur de densité
        
        Args:
            tensor_grid: Grille tensorielle pour analyse
            hint_cache: Cache d'indices pour pondération
            analysis_window_size: Taille de la fenêtre d'analyse (width, height)
            hotspot_threshold: Seuil pour identifier les zones chaudes
            enable_clustering: Activer le clustering des zones chaudes
        """
        self._lock = threading.RLock()
        
        # Dépendances
        self.tensor_grid = tensor_grid
        self.hint_cache = hint_cache
        
        # Configuration
        self.analysis_window_size = analysis_window_size
        self.hotspot_threshold = hotspot_threshold
        self.enable_clustering = enable_clustering
        
        # Cache interne
        self._last_analysis_hash: Optional[str] = None
        self._cached_density_map: Optional[DensityMap] = None
        
        # Statistiques
        self._stats = {
            'analyses_performed': 0,
            'cache_hits': 0,
            'hotspots_identified': 0,
            'average_analysis_time': 0.0
        }
    
    def analyze_density(self, region_bounds: Optional[GridBounds] = None) -> DensityMap:
        """
        Analyse la densité de la grille TensorGrid
        
        Args:
            region_bounds: Bornes de la région à analyser (None = toute la grille)
            
        Returns:
            Carte de densité complète avec zones chaudes et statistiques
        """
        start_time = time.time()
        
        with self._lock:
            # Obtenir la vue solver de TensorGrid
            solver_view = self.tensor_grid.get_solver_view()
            
            # Calculer un hash pour le cache
            view_hash = self._calculate_view_hash(solver_view)
            
            # Vérifier le cache
            if view_hash == self._last_analysis_hash and self._cached_density_map:
                self._stats['cache_hits'] += 1
                return self._cached_density_map
            
            # Définir les bornes d'analyse
            if region_bounds is None:
                region_bounds = GridBounds(
                    solver_view['global_offset'][0],
                    solver_view['global_offset'][1],
                    solver_view['global_offset'][0] + solver_view['symbols'].shape[1] - 1,
                    solver_view['global_offset'][1] + solver_view['symbols'].shape[0] - 1
                )
            
            # Extraire les données pour la région
            symbols = self._extract_region_array(solver_view['symbols'], region_bounds, solver_view['global_offset'])
            frontier_mask = self._extract_region_array(solver_view['frontier_mask'], region_bounds, solver_view['global_offset'])
            confidence = self._extract_region_array(solver_view['confidence'], region_bounds, solver_view['global_offset'])
            
            # Calculer les masques de base
            unknown_mask = (symbols == CellSymbol.UNKNOWN)
            revealed_mask = (symbols != CellSymbol.UNKNOWN) & (symbols != CellSymbol.UNREVEALED)
            numbers_mask = (symbols >= CellSymbol.NUMBER_1) & (symbols <= CellSymbol.NUMBER_8)
            
            # Calculer la grille de densité
            density_grid = self._calculate_density_grid(
                unknown_mask, frontier_mask, numbers_mask, confidence
            )
            
            # Identifier les zones chaudes
            hotspots = self._identify_hotspots(density_grid, region_bounds)
            
            # Segmenter en régions de densité
            regions = self._segment_density_regions(
                density_grid, unknown_mask, frontier_mask, numbers_mask, region_bounds
            )
            
            # Calculer les statistiques globales
            global_stats = self._calculate_global_stats(
                density_grid, unknown_mask, frontier_mask, numbers_mask
            )
            
            # Intégrer les hints si disponibles
            if self.enable_clustering:
                hotspots = self._integrate_hints(hotspots, region_bounds)
            
            # Créer la carte de densité
            density_map = DensityMap(
                global_bounds=region_bounds,
                density_grid=density_grid,
                hotspots=hotspots,
                regions=regions,
                global_stats=global_stats
            )
            
            # Mettre en cache
            self._cached_density_map = density_map
            self._last_analysis_hash = view_hash
            
            # Mettre à jour les statistiques
            analysis_time = time.time() - start_time
            self._update_stats(len(hotspots), analysis_time)
            
            return density_map
    
    def _extract_region_array(self, full_array: np.ndarray, bounds: GridBounds, 
                              offset: Tuple[int, int]) -> np.ndarray:
        """Extrait une région d'un array avec les coordonnées globales"""
        local_y_min = bounds.y_min - offset[1]
        local_y_max = bounds.y_max - offset[1]
        local_x_min = bounds.x_min - offset[0]
        local_x_max = bounds.x_max - offset[0]
        
        height, width = full_array.shape
        local_y_min = max(0, local_y_min)
        local_y_max = min(height - 1, local_y_max)
        local_x_min = max(0, local_x_min)
        local_x_max = min(width - 1, local_x_max)
        
        return full_array[local_y_min:local_y_max+1, local_x_min:local_x_max+1]
    
    def _calculate_density_grid(self, unknown_mask: np.ndarray, frontier_mask: np.ndarray,
                                numbers_mask: np.ndarray, confidence: np.ndarray) -> np.ndarray:
        """Calcule la grille de densité combinée"""
        # Densité de base: frontière + inconnues
        base_density = frontier_mask.astype(float) * 0.6 + unknown_mask.astype(float) * 0.4
        
        # Pondération par la confiance des cellules révélées adjacentes
        if np.any(numbers_mask):
            # Dilater les nombres pour influencer les zones adjacentes
            if HAS_SCIPY:
                from scipy import ndimage
                kernel = np.ones((3, 3), dtype=float)
                confidence_influence = ndimage.convolve(
                    (numbers_mask * confidence).astype(float), kernel, mode='constant'
                ) / 9.0
            else:
                # Fallback numpy: convolution manuelle
                confidence_influence = self._manual_convolve(
                    (numbers_mask * confidence).astype(float), kernel_size=3
                ) / 9.0
            base_density += confidence_influence * 0.3
        
        # Lissage spatial pour éviter les artefacts
        if HAS_SCIPY:
            from scipy import ndimage
            smoothed_density = ndimage.gaussian_filter(base_density, sigma=1.0)
        else:
            # Fallback numpy: lissage manuel
            smoothed_density = self._manual_gaussian_blur(base_density, sigma=1.0)
        
        # Normaliser entre 0 et 1
        if np.max(smoothed_density) > 0:
            normalized_density = smoothed_density / np.max(smoothed_density)
        else:
            normalized_density = smoothed_density
        
        return normalized_density
    
    def _identify_hotspots(self, density_grid: np.ndarray, 
                          bounds: GridBounds) -> List[Tuple[int, int, float]]:
        """Identifie les zones chaudes (points de haute densité)"""
        hotspots = []
        
        # Trouver les points au-dessus du seuil
        high_density_mask = density_grid >= self.hotspot_threshold
        high_density_points = np.where(high_density_mask)
        
        for local_y, local_x in zip(high_density_points[0], high_density_points[1]):
            global_x = bounds.x_min + local_x
            global_y = bounds.y_min + local_y
            density = density_grid[local_y, local_x]
            
            hotspots.append((global_x, global_y, float(density)))
        
        # Regrouper les points proches si clustering activé
        if self.enable_clustering and len(hotspots) > 10:
            hotspots = self._cluster_hotspots(hotspots)
        
        return hotspots
    
    def _cluster_hotspots(self, hotspots: List[Tuple[int, int, float]]) -> List[Tuple[int, int, float]]:
        """Regroupe les zones chaudes proches pour éviter la redondance"""
        if len(hotspots) <= 5:
            return hotspots
        
        # Extraire les coordonnées pour clustering
        coords = np.array([(x, y) for x, y, _ in hotspots])
        densities = np.array([d for _, _, d in hotspots])
        
        # Déterminer le nombre optimal de clusters
        n_clusters = min(len(hotspots) // 3, 8)
        
        try:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(coords)
            
            # Calculer les centroïdes pondérés par densité
            clustered_hotspots = []
            for i in range(n_clusters):
                cluster_mask = cluster_labels == i
                cluster_coords = coords[cluster_mask]
                cluster_densities = densities[cluster_mask]
                
                # Centroïde pondéré
                weighted_center = np.average(cluster_coords, weights=cluster_densities, axis=0)
                avg_density = np.mean(cluster_densities)
                
                clustered_hotspots.append((
                    int(weighted_center[0]),
                    int(weighted_center[1]),
                    float(avg_density)
                ))
            
            return clustered_hotspots
            
        except Exception:
            # Fallback: retourner les hotspots originaux
            return hotspots
    
    def _segment_density_regions(self, density_grid: np.ndarray, unknown_mask: np.ndarray,
                                 frontier_mask: np.ndarray, numbers_mask: np.ndarray,
                                 bounds: GridBounds) -> List[RegionDensity]:
        """Segmente la grille en régions de densité homogène"""
        # Utiliser un seuillage adaptatif pour créer des régions
        threshold = np.percentile(density_grid[density_grid > 0], 70) if np.any(density_grid > 0) else 0.1
        high_density_regions = density_grid >= threshold
        
        # Grouper en régions connexes
        if HAS_SCIPY:
            from scipy import ndimage
            labeled_regions, num_regions = ndimage.label(high_density_regions)
        else:
            # Fallback numpy: étiquetage manuel
            labeled_regions, num_regions = self._manual_label(high_density_regions)
        
        regions = []
        for region_id in range(1, num_regions + 1):
            region_mask = (labeled_regions == region_id)
            region_points = np.where(region_mask)
            
            if len(region_points[0]) < 5:  # Ignorer les très petites régions
                continue
            
            # Calculer les bornes de la région
            local_y_min, local_y_max = region_points[0].min(), region_points[0].max()
            local_x_min, local_x_max = region_points[1].min(), region_points[1].max()
            
            region_bounds = GridBounds(
                x_min=bounds.x_min + local_x_min,
                y_min=bounds.y_min + local_y_min,
                x_max=bounds.x_min + local_x_max,
                y_max=bounds.y_min + local_y_max
            )
            
            # Extraire les statistiques pour la région
            region_unknown = np.sum(unknown_mask[region_mask])
            region_frontier = np.sum(frontier_mask[region_mask])
            region_numbers = np.sum(numbers_mask[region_mask])
            total_cells = np.sum(region_mask)
            
            # Calculer les densités
            frontier_density = region_frontier / total_cells if total_cells > 0 else 0
            unknown_density = region_unknown / total_cells if total_cells > 0 else 0
            critical_density = region_numbers / total_cells if total_cells > 0 else 0
            action_density = (region_frontier + region_numbers) / total_cells if total_cells > 0 else 0
            
            # Complexité et priorité
            complexity = self._calculate_region_complexity(
                frontier_density, unknown_density, critical_density
            )
            priority = self._calculate_region_priority(
                region_frontier, region_unknown, total_cells
            )
            
            region = RegionDensity(
                bounds=region_bounds,
                total_cells=total_cells,
                frontier_cells=region_frontier,
                unknown_cells=region_unknown,
                critical_cells=region_numbers,
                action_opportunities=region_frontier + region_numbers,
                frontier_density=frontier_density,
                unknown_density=unknown_density,
                critical_density=critical_density,
                action_density=action_density,
                complexity_score=complexity,
                priority_weight=priority,
                timestamp=time.time()
            )
            regions.append(region)
        
        # Trier par densité globale décroissante
        return sorted(regions, key=lambda r: r.get_overall_density(), reverse=True)
    
    def _calculate_region_complexity(self, frontier_density: float, 
                                    unknown_density: float, critical_density: float) -> float:
        """Calcule la complexité d'une région"""
        # Complexité basée sur l'équilibre entre les différents types
        balance_score = 1.0 - abs(frontier_density - unknown_density)
        return 0.5 * balance_score + 0.5 * critical_density
    
    def _calculate_region_priority(self, frontier_cells: int, unknown_cells: int, 
                                   total_cells: int) -> float:
        """Calcule la priorité d'une région"""
        if total_cells == 0:
            return 0.0
        
        # Priorité basée sur le ratio d'opportunités d'action
        action_ratio = (frontier_cells + unknown_cells) / total_cells
        
        # Bonus pour les tailles moyennes (ni trop petites, ni trop grandes)
        size_factor = 1.0 - abs(total_cells - 50) / 100.0
        size_factor = max(0.0, size_factor)
        
        return 0.7 * action_ratio + 0.3 * size_factor
    
    def _calculate_global_stats(self, density_grid: np.ndarray, unknown_mask: np.ndarray,
                                frontier_mask: np.ndarray, numbers_mask: np.ndarray) -> Dict[str, float]:
        """Calcule les statistiques globales de densité"""
        total_cells = density_grid.size
        frontier_cells = np.sum(frontier_mask)
        unknown_cells = np.sum(unknown_mask)
        number_cells = np.sum(numbers_mask)
        
        return {
            'total_cells': float(total_cells),
            'frontier_cells': float(frontier_cells),
            'unknown_cells': float(unknown_cells),
            'number_cells': float(number_cells),
            'frontier_ratio': frontier_cells / total_cells if total_cells > 0 else 0.0,
            'unknown_ratio': unknown_cells / total_cells if total_cells > 0 else 0.0,
            'average_density': float(np.mean(density_grid)),
            'max_density': float(np.max(density_grid)),
            'density_std': float(np.std(density_grid))
        }
    
    def _integrate_hints(self, hotspots: List[Tuple[int, int, float]], 
                        bounds: GridBounds) -> List[Tuple[int, int, float]]:
        """Intègre les hints du HintCache dans l'analyse des zones chaudes"""
        # Obtenir les clusters de hints
        hint_clusters = self.hint_cache.get_clusters_by_type()
        
        # Pour chaque cluster, augmenter la densité des zones chaudes nearby
        enhanced_hotspots = []
        
        for x, y, density in hotspots:
            enhanced_density = density
            
            # Vérifier les hints proches
            for cluster in hint_clusters:
                for hx, hy in cluster.cells:
                    # Distance euclidienne
                    dist = ((x - hx) ** 2 + (y - hy) ** 2) ** 0.5
                    
                    if dist < 5.0:  # Influence locale
                        # Augmenter la densité en fonction de la priorité du hint
                        boost = cluster.priority * (1.0 - dist / 5.0) * 0.2
                        enhanced_density = min(1.0, enhanced_density + boost)
            
            enhanced_hotspots.append((x, y, enhanced_density))
        
        return enhanced_hotspots
    
    def _calculate_view_hash(self, solver_view: Dict[str, Any]) -> str:
        """Calcule un hash de la vue solver pour le cache"""
        symbols = solver_view['symbols']
        frontier_mask = solver_view['frontier_mask']
        
        stats = (
            symbols.shape,
            np.sum(symbols == CellSymbol.UNKNOWN),
            np.sum(frontier_mask),
            solver_view['global_offset']
        )
        
        return str(hash(stats))
    
    def _update_stats(self, hotspots_count: int, analysis_time: float) -> None:
        """Met à jour les statistiques de l'analyseur"""
        self._stats['analyses_performed'] += 1
        self._stats['hotspots_identified'] += hotspots_count
        
        total_analyses = self._stats['analyses_performed']
        current_avg = self._stats['average_analysis_time']
        self._stats['average_analysis_time'] = (
            (current_avg * (total_analyses - 1) + analysis_time) / total_analyses
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de l'analyseur"""
        with self._lock:
            stats = self._stats.copy()
            stats.update({
                'tensor_grid_bounds': self.tensor_grid.get_bounds(),
                'has_scipy': HAS_SCIPY,
                'has_sklearn': HAS_SKLEARN,
                'last_analysis_time': self._last_analysis_time
            })
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'analyses_performed': 0,
                'cache_hits': 0,
                'hotspots_identified': 0,
                'average_analysis_time': 0.0
            }
    
    def invalidate_cache(self) -> None:
        """Invalide le cache forçant une nouvelle analyse"""
        with self._lock:
            self._last_analysis_hash = None
            self._cached_density_map = None
