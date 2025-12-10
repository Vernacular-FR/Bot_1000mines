"""
HintCache - File d'événements et cache d'indices pour optimisations (S3)

Gère les DirtySets, clusters et priorités pour optimiser le pipeline:
- Évènements de modification de régions
- Clusters de cellules à traiter en priorité
- Hints pour le solver basés sur les changements
"""

import time
import threading
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import heapq
from collections import defaultdict

from .tensor_grid import GridBounds, CellSymbol


class HintType(Enum):
    """Types d'indices/hints"""
    DIRTY_REGION = "dirty_region"
    FRONTIER_UPDATE = "frontier_update"
    CLUSTER_DISCOVERY = "cluster_discovery"
    PRIORITY_HINT = "priority_hint"
    SOLVER_FEEDBACK = "solver_feedback"


@dataclass
class HintEvent:
    """Événement d'indice avec priorité et métadonnées"""
    hint_type: HintType
    priority: float  # Plus élevé = plus prioritaire
    timestamp: float
    bounds: GridBounds
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """Pour heapq: priorité décroissante"""
        return self.priority > other.priority


@dataclass
class CellCluster:
    """Cluster de cellules connexes à traiter ensemble"""
    cluster_id: str
    cells: Set[Tuple[int, int]]  # Ensemble de coordonnées (x, y)
    center: Tuple[int, int]
    bounds: GridBounds
    priority: float
    hint_type: HintType
    created_at: float
    
    def size(self) -> int:
        return len(self.cells)
    
    def density(self) -> float:
        """Densité du cluster (cells / area)"""
        area = self.bounds.width() * self.bounds.height()
        return self.size() / area if area > 0 else 0.0


class HintCache:
    """
    Cache d'indices et file d'événements pour optimisations
    
    Fonctionnalités:
    - File de priorité des hints pour le solver
    - Clustering automatique des cellules modifiées
    - Gestion des dirty regions
    - Feedback loop avec le solver
    """
    
    def __init__(self, max_hints: int = 1000, max_clusters: int = 100):
        """
        Initialise le cache d'indices
        
        Args:
            max_hints: Nombre maximum de hints en mémoire
            max_clusters: Nombre maximum de clusters
        """
        self._lock = threading.RLock()
        
        # File de priorité des hints
        self._hint_queue: List[HintEvent] = []
        self._max_hints = max_hints
        
        # Clusters actifs
        self._clusters: Dict[str, CellCluster] = {}
        self._max_clusters = max_clusters
        
        # Suivi des dirty regions
        self._dirty_regions: Dict[str, Tuple[GridBounds, float]] = {}
        
        # Statistiques
        self._stats = {
            'hints_processed': 0,
            'clusters_created': 0,
            'hints_dropped': 0,
            'last_cleanup': time.time()
        }
        
        # Thread de nettoyage automatique
        self._cleanup_interval = 60.0  # secondes
        self._last_cleanup = time.time()
    
    def publish_hint(self, hint_type: HintType, bounds: GridBounds, 
                    priority: float = 1.0, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Publie un nouvel hint dans la file
        
        Args:
            hint_type: Type du hint
            bounds: Région concernée
            priority: Priorité (plus élevé = plus urgent)
            metadata: Métadonnées additionnelles
        """
        with self._lock:
            hint = HintEvent(
                hint_type=hint_type,
                priority=priority,
                timestamp=time.time(),
                bounds=bounds,
                metadata=metadata or {}
            )
            
            # Ajouter à la file de priorité
            heapq.heappush(self._hint_queue, hint)
            
            # Limiter la taille de la file
            if len(self._hint_queue) > self._max_hints:
                # Supprimer les hints les moins prioritaires
                self._hint_queue.sort(key=lambda h: h.priority)
                dropped = len(self._hint_queue) - self._max_hints
                self._hint_queue = self._hint_queue[self._max_hints:]
                heapq.heapify(self._hint_queue)
                self._stats['hints_dropped'] += dropped
            
            # Mettre à jour les dirty regions
            if hint_type == HintType.DIRTY_REGION:
                self._dirty_regions[hint_type.value] = (bounds, time.time())
            
            self._stats['hints_processed'] += 1
            
            # Nettoyage périodique
            self._maybe_cleanup()
    
    def create_cluster(self, cells: Set[Tuple[int, int]], hint_type: HintType, 
                      priority: float = 1.0, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Crée un nouveau cluster de cellules
        
        Args:
            cells: Ensemble de coordonnées des cellules
            hint_type: Type associé au cluster
            priority: Priorité du cluster
            metadata: Métadonnées additionnelles
            
        Returns:
            ID du cluster créé
        """
        with self._lock:
            if not cells:
                return ""
            
            # Calculer le centre et les bornes
            x_coords = [x for x, y in cells]
            y_coords = [y for x, y in cells]
            
            center_x = sum(x_coords) / len(x_coords)
            center_y = sum(y_coords) / len(y_coords)
            center = (int(center_x), int(center_y))
            
            bounds = GridBounds(
                x_min=min(x_coords),
                y_min=min(y_coords),
                x_max=max(x_coords),
                y_max=max(y_coords)
            )
            
            # Générer un ID unique
            cluster_id = f"{hint_type.value}_{int(time.time() * 1000)}_{len(cells)}"
            
            # Créer le cluster
            cluster = CellCluster(
                cluster_id=cluster_id,
                cells=cells,
                center=center,
                bounds=bounds,
                priority=priority,
                hint_type=hint_type,
                created_at=time.time()
            )
            
            # Ajouter au cache
            self._clusters[cluster_id] = cluster
            
            # Limiter le nombre de clusters
            if len(self._clusters) > self._max_clusters:
                # Supprimer les clusters les plus anciens/moins prioritaires
                clusters_by_priority = sorted(
                    self._clusters.items(),
                    key=lambda item: (item[1].priority, item[1].created_at)
                )
                to_remove = len(clusters_by_priority) - self._max_clusters
                for i in range(to_remove):
                    del self._clusters[clusters_by_priority[i][0]]
            
            self._stats['clusters_created'] += 1
            
            # Publier un hint pour le cluster
            self.publish_hint(
                hint_type=HintType.CLUSTER_DISCOVERY,
                bounds=bounds,
                priority=priority,
                metadata={
                    'cluster_id': cluster_id,
                    'cell_count': len(cells),
                    'density': cluster.density(),
                    **(metadata or {})
                }
            )
            
            return cluster_id
    
    def get_next_hints(self, max_count: int = 10, min_priority: float = 0.0) -> List[HintEvent]:
        """
        Récupère les prochains hints à traiter
        
        Args:
            max_count: Nombre maximum de hints à retourner
            min_priority: Priorité minimale requise
            
        Returns:
            Liste des hints les plus prioritaires
        """
        with self._lock:
            # Extraire les hints qui respectent les critères
            valid_hints = []
            remaining_hints = []
            
            while self._hint_queue and len(valid_hints) < max_count:
                hint = heapq.heappop(self._hint_queue)
                if hint.priority >= min_priority:
                    valid_hints.append(hint)
                else:
                    remaining_hints.append(hint)
            
            # Remettre les hints non utilisés dans la file
            for hint in remaining_hints:
                heapq.heappush(self._hint_queue, hint)
            
            # Remettre les hints utilisés si nécessaire (pour ne pas les perdre)
            # Dans une implémentation réelle, on les marquerait comme "en cours"
            for hint in valid_hints:
                heapq.heappush(self._hint_queue, hint)
            
            return valid_hints
    
    def get_clusters_by_type(self, hint_type: Optional[HintType] = None) -> List[CellCluster]:
        """
        Récupère les clusters par type
        
        Args:
            hint_type: Type de cluster (None pour tous)
            
        Returns:
            Liste des clusters correspondants
        """
        with self._lock:
            clusters = list(self._clusters.values())
            
            if hint_type is not None:
                clusters = [c for c in clusters if c.hint_type == hint_type]
            
            # Trier par priorité décroissante
            return sorted(clusters, key=lambda c: c.priority, reverse=True)
    
    def get_dirty_regions(self) -> Dict[str, Tuple[GridBounds, float]]:
        """Retourne les dirty regions actives"""
        with self._lock:
            return self._dirty_regions.copy()
    
    def mark_region_processed(self, bounds: GridBounds) -> None:
        """
        Marque une région comme traitée (nettoie les hints associés)
        
        Args:
            bounds: Région qui a été traitée
        """
        with self._lock:
            # Filtrer les hints qui sont dans la région traitée
            remaining_hints = []
            for hint in self._hint_queue:
                if not self._bounds_overlap(hint.bounds, bounds):
                    remaining_hints.append(hint)
            
            self._hint_queue = remaining_hints
            heapq.heapify(self._hint_queue)
            
            # Nettoyer les dirty regions
            to_remove = []
            for key, (dirty_bounds, _) in self._dirty_regions.items():
                if self._bounds_overlap(dirty_bounds, bounds):
                    to_remove.append(key)
            
            for key in to_remove:
                del self._dirty_regions[key]
    
    def solver_feedback(self, solved_bounds: GridBounds, success_rate: float,
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Feedback du solver pour ajuster les priorités futures
        
        Args:
            solved_bounds: Région qui a été résolue
            success_rate: Taux de succès (0.0..1.0)
            metadata: Métadonnées additionnelles
        """
        with self._lock:
            # Publier un hint de feedback
            self.publish_hint(
                hint_type=HintType.SOLVER_FEEDBACK,
                bounds=solved_bounds,
                priority=success_rate,
                metadata={
                    'success_rate': success_rate,
                    'feedback_type': 'solver_result',
                    **(metadata or {})
                }
            )
            
            # Ajuster la priorité des clusters proches
            for cluster in self._clusters.values():
                if self._bounds_overlap(cluster.bounds, solved_bounds):
                    # Réduire la priorité des clusters déjà traités
                    cluster.priority *= (1.0 - success_rate * 0.5)
    
    def _bounds_overlap(self, bounds1: GridBounds, bounds2: GridBounds) -> bool:
        """Vérifie si deux bornes se chevauchent"""
        return not (bounds1.x_max < bounds2.x_min or 
                   bounds2.x_max < bounds1.x_min or
                   bounds1.y_max < bounds2.y_min or 
                   bounds2.y_max < bounds1.y_min)
    
    def _maybe_cleanup(self) -> None:
        """Nettoyage périodique des anciens hints/clusters"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        # Supprimer les hints très anciens (> 5 minutes)
        cutoff_time = current_time - 300.0
        self._hint_queue = [h for h in self._hint_queue if h.timestamp > cutoff_time]
        heapq.heapify(self._hint_queue)
        
        # Supprimer les clusters anciens ou à faible priorité
        to_remove = []
        for cluster_id, cluster in self._clusters.items():
            if (cluster.created_at < cutoff_time and 
                cluster.priority < 0.1):
                to_remove.append(cluster_id)
        
        for cluster_id in to_remove:
            del self._clusters[cluster_id]
        
        # Nettoyer les dirty regions anciennes
        to_remove = []
        for key, (bounds, timestamp) in self._dirty_regions.items():
            if timestamp < cutoff_time:
                to_remove.append(key)
        
        for key in to_remove:
            del self._dirty_regions[key]
        
        self._last_cleanup = current_time
        self._stats['last_cleanup'] = current_time
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache"""
        with self._lock:
            return {
                **self._stats,
                'hint_queue_size': len(self._hint_queue),
                'cluster_count': len(self._clusters),
                'dirty_regions_count': len(self._dirty_regions),
                'memory_estimate': (
                    len(self._hint_queue) * 200 +  # estimation par hint
                    len(self._clusters) * 100 +   # estimation par cluster
                    len(self._dirty_regions) * 50  # estimation par dirty region
                )
            }
    
    def clear_all(self) -> None:
        """Vide complètement le cache"""
        with self._lock:
            self._hint_queue.clear()
            self._clusters.clear()
            self._dirty_regions.clear()
            self._stats = {
                'hints_processed': 0,
                'clusters_created': 0,
                'hints_dropped': 0,
                'last_cleanup': time.time()
            }
