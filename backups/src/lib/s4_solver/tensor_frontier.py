"""
TensorFrontier - Adaptateur pour exploitation des frontières TensorGrid (S4)

Interface fine entre S2 Reconnaissance et S4 Solver:
- Lit le frontier_mask depuis TensorGrid
- Extrait et organise les zones de frontière
- Fournit des structures optimisées pour le CSP
- Maintient la cohérence avec les hints du HintCache
"""

import numpy as np
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time
import threading

from ..s3_tensor.tensor_grid import TensorGrid, GridBounds, CellSymbol
from ..s3_tensor.hint_cache import HintCache, HintType, CellCluster


class FrontierZoneType(Enum):
    """Types de zones de frontière pour le solver"""
    CSP_SOLVABLE = "csp_solvable"  # Zone résoluble par CSP exact
    MONTE_CARLO = "monte_carlo"    # Zone nécessitant Monte Carlo
    NEURAL_ASSIST = "neural_assist"  # Zone pour assistance neurale
    TRIVIAL = "trivial"            # Zone trivial (toutes sûres/mines)


@dataclass
class FrontierZone:
    """Zone de frontière structurée pour le solver"""
    zone_id: str
    zone_type: FrontierZoneType
    bounds: GridBounds
    unknown_cells: Set[Tuple[int, int]]     # Cellules à résoudre
    number_cells: Dict[Tuple[int, int], int]  # Cellules nombres → valeur
    safe_cells: Set[Tuple[int, int]]       # Cellules sûres identifiées
    mine_cells: Set[Tuple[int, int]]       # Cellules mines identifiées
    complexity_score: float
    priority: float
    metadata: Dict[str, Any]
    
    def size(self) -> int:
        return len(self.unknown_cells)
    
    def constraint_density(self) -> float:
        """Densité de contraintes (nombres / inconnues)"""
        if len(self.unknown_cells) == 0:
            return 0.0
        return len(self.number_cells) / len(self.unknown_cells)
    
    def is_trivial(self) -> bool:
        """Vérifie si la zone est trivialement résoluble"""
        return (len(self.safe_cells) > 0 or len(self.mine_cells) > 0) and len(self.unknown_cells) == 0


@dataclass
class SolverContext:
    """Contexte complet pour le solver"""
    tensor_grid: TensorGrid
    hint_cache: HintCache
    global_bounds: GridBounds
    frontier_zones: List[FrontierZone]
    total_unknown: int
    total_frontier: int
    processing_time: float
    metadata: Dict[str, Any]


class TensorFrontier:
    """
    Adaptateur TensorGrid → Solver avec optimisations
    
    Fonctionnalités:
    - Extraction des frontières depuis TensorGrid
    - Segmentation en zones résolubles
    - Classification par type de solver approprié
    - Intégration avec les hints du HintCache
    """
    
    def __init__(self, tensor_grid: TensorGrid, hint_cache: HintCache,
                 min_zone_size: int = 1, max_zone_size: int = 50,
                 enable_hint_integration: bool = True):
        """
        Initialise l'adaptateur TensorFrontier
        
        Args:
            tensor_grid: Grille tensorielle source
            hint_cache: Cache d'indices pour optimisations
            min_zone_size: Taille minimale d'une zone
            max_zone_size: Taille maximale d'une zone
            enable_hint_integration: Activer l'intégration des hints
        """
        self._lock = threading.RLock()
        
        # Dépendances
        self.tensor_grid = tensor_grid
        self.hint_cache = hint_cache
        
        # Configuration
        self.min_zone_size = min_zone_size
        self.max_zone_size = max_zone_size
        self.enable_hint_integration = enable_hint_integration
        
        # Cache interne pour éviter les re-traitements
        self._last_solver_view_hash: Optional[str] = None
        self._cached_context: Optional[SolverContext] = None
        
        # Statistiques
        self._stats = {
            'extractions_performed': 0,
            'zones_created': 0,
            'cache_hits': 0,
            'processing_time': 0.0,
            'last_extraction': time.time()
        }
    
    def extract_solver_context(self, region_bounds: Optional[GridBounds] = None) -> SolverContext:
        """
        Extrait un contexte complet pour le solver
        
        Args:
            region_bounds: Bornes de la région à analyser (None = toute la grille)
            
        Returns:
            Contexte structuré pour le solver
        """
        start_time = time.time()
        
        with self._lock:
            # Obtenir la vue solver de TensorGrid
            solver_view = self.tensor_grid.get_solver_view()
            
            # Calculer un hash de la vue pour le cache
            view_hash = self._calculate_view_hash(solver_view)
            
            # Vérifier le cache
            if (view_hash == self._last_solver_view_hash and 
                self._cached_context is not None):
                self._stats['cache_hits'] += 1
                return self._cached_context
            
            # Définir les bornes globales
            if region_bounds is None:
                region_bounds = GridBounds(
                    solver_view['global_offset'][0],
                    solver_view['global_offset'][1],
                    solver_view['global_offset'][0] + solver_view['symbols'].shape[1] - 1,
                    solver_view['global_offset'][1] + solver_view['symbols'].shape[0] - 1
                )
            
            # Extraire et segmenter les frontières
            frontier_zones = self._extract_frontier_zones(solver_view, region_bounds)
            
            # Intégrer les hints si activé
            if self.enable_hint_integration:
                frontier_zones = self._integrate_hints(frontier_zones, region_bounds)
            
            # Calculer les statistiques globales
            total_unknown = np.sum(solver_view['symbols'] == CellSymbol.UNKNOWN)
            total_frontier = np.sum(solver_view['frontier_mask'])
            
            # Créer le contexte
            context = SolverContext(
                tensor_grid=self.tensor_grid,
                hint_cache=self.hint_cache,
                global_bounds=region_bounds,
                frontier_zones=frontier_zones,
                total_unknown=total_unknown,
                total_frontier=total_frontier,
                processing_time=time.time() - start_time,
                metadata={
                    'extraction_time': time.time(),
                    'solver_version': '1.0',
                    'view_hash': view_hash
                }
            )
            
            # Mettre en cache
            self._cached_context = context
            self._last_solver_view_hash = view_hash
            
            # Mettre à jour les statistiques
            self._stats['extractions_performed'] += 1
            self._stats['zones_created'] += len(frontier_zones)
            self._stats['processing_time'] += time.time() - start_time
            self._stats['last_extraction'] = time.time()
            
            return context
    
    def _extract_frontier_zones(self, solver_view: Dict[str, Any], 
                               bounds: GridBounds) -> List[FrontierZone]:
        """Extrait et segmente les zones de frontière"""
        symbols = solver_view['symbols']
        frontier_mask = solver_view['frontier_mask']
        global_offset = solver_view['global_offset']
        
        # Identifier les cellules pertinentes
        unknown_mask = (symbols == CellSymbol.UNKNOWN)
        numbers_mask = (symbols >= CellSymbol.NUMBER_1) & (symbols <= CellSymbol.NUMBER_8)
        
        # Extraire uniquement les cellules de frontière
        frontier_unknown = unknown_mask & frontier_mask
        
        if not np.any(frontier_unknown):
            return []
        
        # Segmenter en zones connexes
        from scipy import ndimage
        labeled_zones, num_zones = ndimage.label(frontier_unknown)
        
        zones = []
        for zone_id in range(1, num_zones + 1):
            zone_cells = np.where(labeled_zones == zone_id)
            
            if len(zone_cells[0]) < self.min_zone_size:
                continue
            if len(zone_cells[0]) > self.max_zone_size:
                continue
            
            # Extraire les cellules de la zone
            unknown_coords = set()
            number_coords = {}
            
            for local_y, local_x in zip(zone_cells[0], zone_cells[1]):
                global_x = global_offset[0] + local_x
                global_y = global_offset[1] + local_y
                
                if frontier_unknown[local_y, local_x]:
                    unknown_coords.add((global_x, global_y))
                
                # Chercher les nombres adjacents
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if dy == 0 and dx == 0:
                            continue
                        ny, nx = local_y + dy, local_x + dx
                        if (0 <= ny < symbols.shape[0] and 
                            0 <= nx < symbols.shape[1] and 
                            numbers_mask[ny, nx]):
                            adj_global_x = global_offset[0] + nx
                            adj_global_y = global_offset[1] + ny
                            number_value = int(symbols[ny, nx]) - 3  # Convertir NUMBER_1(4) → 1
                            number_coords[(adj_global_x, adj_global_y)] = number_value
            
            # Créer la zone
            if unknown_coords and number_coords:
                zone = self._create_frontier_zone(
                    zone_id, unknown_coords, number_coords, bounds
                )
                zones.append(zone)
        
        return zones
    
    def _create_frontier_zone(self, zone_id: int, unknown_coords: Set[Tuple[int, int]],
                             number_coords: Dict[Tuple[int, int], int],
                             bounds: GridBounds) -> FrontierZone:
        """Crée une zone de frontière structurée"""
        # Calculer les bornes de la zone
        all_coords = unknown_coords.union(set(number_coords.keys()))
        x_coords = [x for x, y in all_coords]
        y_coords = [y for x, y in all_coords]
        
        zone_bounds = GridBounds(
            x_min=min(x_coords),
            y_min=min(y_coords),
            x_max=max(x_coords),
            y_max=max(y_coords)
        )
        
        # Analyser la complexité et déterminer le type
        complexity = self._calculate_zone_complexity(unknown_coords, number_coords)
        zone_type = self._classify_zone_type(unknown_coords, number_coords, complexity)
        priority = self._calculate_zone_priority(unknown_coords, number_coords, complexity)
        
        return FrontierZone(
            zone_id=f"zone_{zone_id}_{int(time.time() * 1000)}",
            zone_type=zone_type,
            bounds=zone_bounds,
            unknown_cells=unknown_coords,
            number_cells=number_coords,
            safe_cells=set(),  # Sera rempli par le solver
            mine_cells=set(),  # Sera rempli par le solver
            complexity_score=complexity,
            priority=priority,
            metadata={
                'creation_time': time.time(),
                'extraction_method': 'tensor_frontier'
            }
        )
    
    def _calculate_zone_complexity(self, unknown_coords: Set[Tuple[int, int]],
                                  number_coords: Dict[Tuple[int, int], int]) -> float:
        """Calcule la complexité d'une zone"""
        if not unknown_coords:
            return 0.0
        
        # Facteurs de complexité:
        # 1. Ratio nombres/inconnues
        # 2. Valeur moyenne des nombres
        # 3. Densité spatiale
        
        ratio = len(number_coords) / len(unknown_coords)
        avg_number_value = np.mean(list(number_coords.values())) if number_coords else 0
        
        # Complexité combinée
        complexity = 0.3 * ratio + 0.4 * (avg_number_value / 8.0) + 0.3 * min(len(unknown_coords) / 20.0, 1.0)
        return min(complexity, 1.0)
    
    def _classify_zone_type(self, unknown_coords: Set[Tuple[int, int]],
                           number_coords: Dict[Tuple[int, int], int],
                           complexity: float) -> FrontierZoneType:
        """Classifie le type de solver approprié pour la zone"""
        if not unknown_coords:
            return FrontierZoneType.TRIVIAL
        
        if complexity < 0.3:
            return FrontierZoneType.CSP_SOLVABLE
        elif complexity < 0.7:
            return FrontierZoneType.MONTE_CARLO
        else:
            return FrontierZoneType.NEURAL_ASSIST
    
    def _calculate_zone_priority(self, unknown_coords: Set[Tuple[int, int]],
                                number_coords: Dict[Tuple[int, int], int],
                                complexity: float) -> float:
        """Calcule la priorité d'une zone"""
        if not unknown_coords:
            return 0.0
        
        # Priorité basée sur:
        # 1. Taille (zones moyennes plus prioritaires)
        # 2. Complexité (zones simples plus prioritaires)
        # 3. Densité de contraintes
        
        size_factor = 1.0 - abs(len(unknown_coords) - 10) / 20.0  # Optimal autour de 10
        size_factor = max(0.0, size_factor)
        
        constraint_density = len(number_coords) / len(unknown_coords)
        density_factor = min(constraint_density / 2.0, 1.0)
        
        priority = 0.4 * size_factor + 0.3 * (1.0 - complexity) + 0.3 * density_factor
        return max(0.1, min(priority, 1.0))
    
    def _integrate_hints(self, zones: List[FrontierZone], bounds: GridBounds) -> List[FrontierZone]:
        """Intègre les hints du HintCache dans les zones"""
        if not self.enable_hint_integration:
            return zones
        
        # Obtenir les clusters de hints
        hint_clusters = self.hint_cache.get_clusters_by_type()
        
        # Pour chaque cluster, ajuster les zones correspondantes
        for cluster in hint_clusters:
            cluster_cells = cluster.cells
            
            # Trouver les zones qui intersectent le cluster
            for zone in zones:
                zone_cells = zone.unknown_coords
                
                # Vérifier l'intersection
                intersection = zone_cells.intersection(cluster_cells)
                if intersection:
                    # Ajuster la priorité de la zone
                    priority_boost = len(intersection) / len(zone_cells) * cluster.priority
                    zone.priority = min(1.0, zone.priority + priority_boost * 0.3)
                    
                    # Ajouter les métadonnées du cluster
                    zone.metadata.update({
                        'hint_cluster_id': cluster.cluster_id,
                        'hint_priority_boost': priority_boost,
                        'hint_intersection_size': len(intersection)
                    })
        
        # Trier par priorité décroissante
        return sorted(zones, key=lambda z: z.priority, reverse=True)
    
    def _calculate_view_hash(self, solver_view: Dict[str, Any]) -> str:
        """Calcule un hash de la vue solver pour le cache"""
        # Hash simple basé sur les shapes et quelques statistiques
        symbols = solver_view['symbols']
        frontier_mask = solver_view['frontier_mask']
        
        stats = (
            symbols.shape,
            np.sum(symbols == CellSymbol.UNKNOWN),
            np.sum(frontier_mask),
            solver_view['global_offset']
        )
        
        return str(hash(stats))
    
    def get_zones_by_type(self, zone_type: FrontierZoneType) -> List[FrontierZone]:
        """
        Récupère les zones d'un type spécifique depuis le dernier contexte
        
        Args:
            zone_type: Type de zone désiré
            
        Returns:
            Liste des zones du type spécifié
        """
        if self._cached_context is None:
            return []
        
        return [zone for zone in self._cached_context.frontier_zones if zone.zone_type == zone_type]
    
    def get_high_priority_zones(self, min_priority: float = 0.5) -> List[FrontierZone]:
        """
        Récupère les zones à haute priorité
        
        Args:
            min_priority: Priorité minimale requise
            
        Returns:
            Liste des zones à haute priorité
        """
        if self._cached_context is None:
            return []
        
        return [zone for zone in self._cached_context.frontier_zones if zone.priority >= min_priority]
    
    def invalidate_cache(self) -> None:
        """Invalide le cache forçant une nouvelle extraction"""
        with self._lock:
            self._last_solver_view_hash = None
            self._cached_context = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de l'adaptateur"""
        with self._lock:
            cache_hit_ratio = (
                self._stats['cache_hits'] / 
                max(self._stats['extractions_performed'], 1)
            )
            
            return {
                **self._stats,
                'cache_hit_ratio': cache_hit_ratio,
                'cached_context_available': self._cached_context is not None,
                'current_zones_count': len(self._cached_context.frontier_zones) if self._cached_context else 0
            }
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'extractions_performed': 0,
                'zones_created': 0,
                'cache_hits': 0,
                'processing_time': 0.0,
                'last_extraction': time.time()
            }
