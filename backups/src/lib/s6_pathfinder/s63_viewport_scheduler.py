"""
ViewportScheduler - Ordonnanceur de viewport pour Pathfinder (S6.3)

Gère les zones hors-champ et les captures complémentaires:
- File des zones à revisiter hors du viewport actuel
- Déclenchement de captures additionnelles si nécessaire
- Optimisation de l'ordre de visite des zones
- Intégration avec PathPlanner pour mouvements coordonnés
"""

import numpy as np
import heapq
import math
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
from collections import defaultdict

from .s62_path_planner import PathPlanner, MovementVector, PathPriority
from .s61_density_analyzer import DensityAnalyzer, DensityMap, RegionDensity
from ..s3_tensor.tensor_grid import TensorGrid, GridBounds, CellSymbol
from ..s3_tensor.hint_cache import HintCache


class VisitStatus(Enum):
    """Statuts de visite des zones"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    POSTPONED = "postponed"


class CaptureTrigger(Enum):
    """Déclencheurs de capture additionnelle"""
    DENSITY_SPIKE = "density_spike"  # Explosion de densité
    FRONTIER_EXPANSION = "frontier_expansion"  # Expansion rapide de frontière
    CRITICAL_ZONE = "critical_zone"  # Zone critique découverte
    TIMEOUT = "timeout"  # Timeout sans nouvelles données
    MANUAL = "manual"  # Déclenchement manuel


@dataclass
class ViewportTask:
    """Tâche de viewport à exécuter"""
    task_id: str
    target_bounds: GridBounds
    priority: float  # 0.0..1.0
    status: VisitStatus
    created_time: float
    scheduled_time: Optional[float] = None
    completion_time: Optional[float] = None
    
    # Métadonnées
    trigger: CaptureTrigger = CaptureTrigger.MANUAL
    reasoning: str = ""
    estimated_duration: float = 0.0
    retry_count: int = 0
    max_retries: int = 3
    
    # Dépendances
    depends_on: List[str] = field(default_factory=list)
    enables_tasks: List[str] = field(default_factory=list)
    
    def __lt__(self, other):
        """Pour le tri par priorité (heapq)"""
        return self.priority > other.priority  # Ordre décroissant


@dataclass
class CaptureRequest:
    """Requête de capture additionnelle"""
    request_id: str
    region_bounds: GridBounds
    trigger: CaptureTrigger
    priority: PathPriority
    reasoning: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class ViewportScheduler:
    """
    Ordonnanceur de viewport pour la gestion des zones hors-champ
    
    Fonctionnalités:
    - File de priorité pour les zones à visiter
    - Détection automatique des besoins de capture additionnelle
    - Optimisation de l'ordre de visite
    - Coordination avec PathPlanner pour mouvements efficaces
    """
    
    def __init__(self, tensor_grid: TensorGrid, hint_cache: HintCache,
                 density_analyzer: DensityAnalyzer, path_planner: PathPlanner,
                 max_pending_tasks: int = 20,
                 task_timeout: float = 30.0,
                 enable_adaptive_scheduling: bool = True):
        """
        Initialise l'ordonnanceur de viewport
        
        Args:
            tensor_grid: Grille tensorielle pour état global
            hint_cache: Cache d'indices pour optimisations
            density_analyzer: Analyseur de densité pour détection
            path_planner: Planificateur pour coordination
            max_pending_tasks: Nombre maximum de tâches en attente
            task_timeout: Timeout pour les tâches en cours
            enable_adaptive_scheduling: Activer l'ordonnancement adaptatif
        """
        self._lock = threading.RLock()
        
        # Dépendances
        self.tensor_grid = tensor_grid
        self.hint_cache = hint_cache
        self.density_analyzer = density_analyzer
        self.path_planner = path_planner
        
        # Configuration
        self.max_pending_tasks = max_pending_tasks
        self.task_timeout = task_timeout
        self.enable_adaptive_scheduling = enable_adaptive_scheduling
        
        # Files et états
        self._task_queue: List[ViewportTask] = []  # Heap de priorité
        self._pending_tasks: Dict[str, ViewportTask] = {}
        self._completed_tasks: Dict[str, ViewportTask] = {}
        self._failed_tasks: Dict[str, ViewportTask] = {}
        
        # État courant
        self._current_viewport: Optional[GridBounds] = None
        self._last_capture_time: float = 0.0
        self._capture_requests: List[CaptureRequest] = []
        
        # Compteurs
        self._task_counter: int = 0
        self._request_counter: int = 0
        
        # Statistiques
        self._stats = {
            'tasks_created': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'captures_triggered': 0,
            'average_task_duration': 0.0,
            'scheduling_efficiency': 0.0
        }
    
    def update_viewport(self, viewport_bounds: GridBounds) -> List[ViewportTask]:
        """
        Met à jour le viewport actuel et retourne les tâches à exécuter
        
        Args:
            viewport_bounds: Nouvelles bornes du viewport
            
        Returns:
            Liste des tâches qui devraient être exécutées maintenant
        """
        with self._lock:
            self._current_viewport = viewport_bounds
            
            # Nettoyer les tâches expirées
            self._cleanup_expired_tasks()
            
            # Détecter les besoins de capture additionnelle
            self._detect_capture_needs(viewport_bounds)
            
            # Mettre à jour les priorités des tâches existantes
            self._update_task_priorities(viewport_bounds)
            
            # Sélectionner les tâches à exécuter
            ready_tasks = self._select_ready_tasks(viewport_bounds)
            
            return ready_tasks
    
    def schedule_zone_visit(self, target_bounds: GridBounds, priority: float = 0.5,
                           trigger: CaptureTrigger = CaptureTrigger.MANUAL,
                           reasoning: str = "", depends_on: List[str] = None) -> str:
        """
        Planifie la visite d'une zone spécifique
        
        Args:
            target_bounds: Bornes de la zone à visiter
            priority: Priorité de la tâche (0.0..1.0)
            trigger: Déclencheur de la tâche
            reasoning: Raison de la visite
            depends_on: Liste des IDs de tâches dépendantes
            
        Returns:
            ID de la tâche créée
        """
        with self._lock:
            # Vérifier si une tâche similaire existe déjà
            existing_task = self._find_similar_task(target_bounds)
            if existing_task:
                # Mettre à jour la priorité si nécessaire
                if priority > existing_task.priority:
                    existing_task.priority = priority
                    heapq.heapify(self._task_queue)
                return existing_task.task_id
            
            # Limiter le nombre de tâches en attente
            if len(self._pending_tasks) >= self.max_pending_tasks:
                self._prune_low_priority_tasks()
            
            # Créer la nouvelle tâche
            task_id = f"viewport_task_{self._task_counter}"
            self._task_counter += 1
            
            task = ViewportTask(
                task_id=task_id,
                target_bounds=target_bounds,
                priority=priority,
                status=VisitStatus.PENDING,
                created_time=time.time(),
                trigger=trigger,
                reasoning=reasoning or f"Visit zone {target_bounds}",
                depends_on=depends_on or []
            )
            
            # Ajouter à la file et au dictionnaire
            heapq.heappush(self._task_queue, task)
            self._pending_tasks[task_id] = task
            
            # Mettre à jour les statistiques
            self._stats['tasks_created'] += 1
            
            return task_id
    
    def complete_task(self, task_id: str, success: bool = True, 
                     metadata: Dict[str, Any] = None) -> None:
        """
        Marque une tâche comme complétée (ou échouée)
        
        Args:
            task_id: ID de la tâche à compléter
            success: True si succès, False si échec
            metadata: Métadonnées additionnelles sur le résultat
        """
        with self._lock:
            task = self._pending_tasks.get(task_id)
            if not task:
                return
            
            task.completion_time = time.time()
            
            if success:
                task.status = VisitStatus.COMPLETED
                self._completed_tasks[task_id] = task
                self._stats['tasks_completed'] += 1
                
                # Activer les tâches qui dépendent de celle-ci
                self._enable_dependent_tasks(task_id)
                
            else:
                task.status = VisitStatus.FAILED
                task.retry_count += 1
                
                if task.retry_count < task.max_retries:
                    # Réessayer plus tard avec priorité réduite
                    task.status = VisitStatus.POSTPONED
                    task.priority *= 0.7
                    task.scheduled_time = time.time() + 5.0  # Attendre 5 secondes
                    heapq.heappush(self._task_queue, task)
                else:
                    self._failed_tasks[task_id] = task
                    self._stats['tasks_failed'] += 1
            
            # Retirer des tâches en attente
            self._pending_tasks.pop(task_id, None)
            
            # Mettre à jour les statistiques de durée
            if task.completion_time and task.created_time:
                duration = task.completion_time - task.created_time
                self._update_duration_stats(duration)
    
    def get_capture_requests(self) -> List[CaptureRequest]:
        """Retourne les requêtes de capture additionnelle en attente"""
        with self._lock:
            # Filtrer les requêtes récentes
            current_time = time.time()
            recent_requests = [
                req for req in self._capture_requests
                if current_time - req.timestamp < 60.0  # Garder 1 minute
            ]
            
            self._capture_requests = recent_requests
            return recent_requests.copy()
    
    def _detect_capture_needs(self, viewport_bounds: GridBounds) -> None:
        """Détecte automatiquement les besoins de capture additionnelle"""
        current_time = time.time()
        
        # Analyser la densité actuelle
        density_map = self.density_analyzer.analyze_density()
        
        # 1. Détection de pic de densité
        if self._detect_density_spike(density_map):
            self._trigger_capture_request(
                region_bounds=self._find_spike_region(density_map),
                trigger=CaptureTrigger.DENSITY_SPIKE,
                priority=PathPriority.HIGH,
                reasoning="Density spike detected"
            )
        
        # 2. Expansion de frontière
        if self._detect_frontier_expansion(density_map):
            self._trigger_capture_request(
                region_bounds=self._find_expansion_region(density_map),
                trigger=CaptureTrigger.FRONTIER_EXPANSION,
                priority=PathPriority.MEDIUM,
                reasoning="Frontier expansion detected"
            )
        
        # 3. Zones critiques hors viewport
        critical_zones = self._find_critical_zones_outside_viewport(density_map, viewport_bounds)
        for zone_bounds in critical_zones:
            self._trigger_capture_request(
                region_bounds=zone_bounds,
                trigger=CaptureTrigger.CRITICAL_ZONE,
                priority=PathPriority.CRITICAL,
                reasoning="Critical zone outside viewport"
            )
        
        # 4. Timeout sans nouvelles données
        if current_time - self._last_capture_time > 15.0:  # 15 secondes
            self._trigger_capture_request(
                region_bounds=self._suggest_exploration_area(),
                trigger=CaptureTrigger.TIMEOUT,
                priority=PathPriority.LOW,
                reasoning="Timeout - need fresh data"
            )
    
    def _detect_density_spike(self, density_map: DensityMap) -> bool:
        """Détecte un pic soudain de densité"""
        if not hasattr(self, '_last_max_density'):
            self._last_max_density = 0.0
            return False
        
        current_max = density_map.global_stats.get('max_density', 0)
        spike_threshold = 0.3  # Augmentation de 30%
        
        if current_max > self._last_max_density + spike_threshold:
            self._last_max_density = current_max
            return True
        
        self._last_max_density = current_max
        return False
    
    def _detect_frontier_expansion(self, density_map: DensityMap) -> bool:
        """Détecte une expansion rapide de la frontière"""
        if not hasattr(self, '_last_frontier_ratio'):
            self._last_frontier_ratio = 0.0
            return False
        
        current_ratio = density_map.global_stats.get('frontier_ratio', 0)
        expansion_threshold = 0.2  # Augmentation de 20%
        
        if current_ratio > self._last_frontier_ratio + expansion_threshold:
            self._last_frontier_ratio = current_ratio
            return True
        
        self._last_frontier_ratio = current_ratio
        return False
    
    def _find_spike_region(self, density_map: DensityMap) -> GridBounds:
        """Trouve la région responsable du pic de densité"""
        highest_point = density_map.get_highest_density_point()
        if not highest_point:
            return density_map.global_bounds
        
        x, y, _ = highest_point
        
        # Retourner une région autour du point de densité maximale
        region_size = 20
        return GridBounds(
            x_min=max(density_map.global_bounds.x_min, x - region_size),
            y_min=max(density_map.global_bounds.y_min, y - region_size),
            x_max=min(density_map.global_bounds.x_max, x + region_size),
            y_max=min(density_map.global_bounds.y_max, y + region_size)
        )
    
    def _find_expansion_region(self, density_map: DensityMap) -> GridBounds:
        """Trouve la région d'expansion de frontière"""
        # Chercher les zones de haute densité en périphérie
        if not density_map.hotspots:
            return density_map.global_bounds
        
        # Prendre les zones chaudes les plus externes
        center_x = (density_map.global_bounds.x_min + density_map.global_bounds.x_max) // 2
        center_y = (density_map.global_bounds.y_min + density_map.global_bounds.y_max) // 2
        
        # Calculer la distance du centre pour chaque hotspot
        distant_hotspots = [
            (x, y, d) for x, y, d in density_map.hotspots
            if math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2) > 50
        ]
        
        if distant_hotspots:
            # Prendre le plus distant
            farthest = max(distant_hotspots, key=lambda h: math.sqrt((h[0] - center_x) ** 2 + (h[1] - center_y) ** 2))
            x, y, _ = farthest
            
            return GridBounds(
                x_min=max(density_map.global_bounds.x_min, x - 15),
                y_min=max(density_map.global_bounds.y_min, y - 15),
                x_max=min(density_map.global_bounds.x_max, x + 15),
                y_max=min(density_map.global_bounds.y_max, y + 15)
            )
        
        return density_map.global_bounds
    
    def _find_critical_zones_outside_viewport(self, density_map: DensityMap, 
                                             viewport_bounds: GridBounds) -> List[GridBounds]:
        """Trouve les zones critiques hors du viewport actuel"""
        critical_zones = []
        
        for region in density_map.regions:
            if (region.get_overall_density() > 0.7 and 
                not self._bounds_in_viewport(region.bounds, viewport_bounds)):
                critical_zones.append(region.bounds)
        
        return critical_zones
    
    def _suggest_exploration_area(self) -> GridBounds:
        """Suggère une zone d'exploration pour le timeout"""
        if not self._current_viewport:
            # Pas de viewport actuel, utiliser le centre de la grille
            solver_view = self.tensor_grid.get_solver_view()
            if solver_view['symbols'].size > 0:
                h, w = solver_view['symbols'].shape
                offset = solver_view['global_offset']
                return GridBounds(
                    x_min=offset[0], y_min=offset[1],
                    x_max=offset[0] + w - 1, y_max=offset[1] + h - 1
                )
        
        # Explorer en spirale autour du viewport actuel
        if self._current_viewport:
            # Déplacement en spirale
            spiral_offset = len(self._capture_requests) * 30
            angle = (len(self._capture_requests) * 45) % 360
            
            center_x = (self._current_viewport.x_min + self._current_viewport.x_max) // 2
            center_y = (self._current_viewport.y_min + self._current_viewport.y_max) // 2
            
            target_x = center_x + int(spiral_offset * math.cos(math.radians(angle)))
            target_y = center_y + int(spiral_offset * math.sin(math.radians(angle)))
            
            return GridBounds(
                x_min=target_x - 25, y_min=target_y - 25,
                x_max=target_x + 25, y_max=target_y + 25
            )
        
        # Fallback: zone vide
        return GridBounds(0, 0, 50, 50)
    
    def _trigger_capture_request(self, region_bounds: GridBounds, trigger: CaptureTrigger,
                                priority: PathPriority, reasoning: str) -> None:
        """Déclenche une requête de capture additionnelle"""
        request_id = f"capture_req_{self._request_counter}"
        self._request_counter += 1
        
        request = CaptureRequest(
            request_id=request_id,
            region_bounds=region_bounds,
            trigger=trigger,
            priority=priority,
            reasoning=reasoning,
            timestamp=time.time()
        )
        
        self._capture_requests.append(request)
        self._stats['captures_triggered'] += 1
    
    def _update_task_priorities(self, viewport_bounds: GridBounds) -> None:
        """Met à jour les priorités des tâches en fonction du viewport"""
        for task in self._pending_tasks.values():
            if task.status == VisitStatus.PENDING:
                # Calculer la distance au viewport
                distance = self._calculate_distance_to_viewport(task.target_bounds, viewport_bounds)
                
                # Ajuster la priorité en fonction de la distance
                distance_factor = max(0.1, 1.0 - distance / 200.0)  # Décroissance avec la distance
                task.priority = min(1.0, task.priority * distance_factor)
        
        # Reconstruire le heap
        self._task_queue = list(self._pending_tasks.values())
        heapq.heapify(self._task_queue)
    
    def _select_ready_tasks(self, viewport_bounds: GridBounds) -> List[ViewportTask]:
        """Sélectionne les tâches prêtes à être exécutées"""
        ready_tasks = []
        current_time = time.time()
        
        # Extraire les tâches prêtes du heap
        temp_tasks = []
        
        while self._task_queue and len(ready_tasks) < 3:  # Limiter à 3 tâches simultanées
            task = heapq.heappop(self._task_queue)
            
            # Vérifier si la tâche est toujours en attente
            if task.task_id not in self._pending_tasks:
                continue
            
            # Vérifier les dépendances
            if not self._dependencies_satisfied(task):
                temp_tasks.append(task)
                continue
            
            # Vérifier si le timing est bon
            if task.scheduled_time and task.scheduled_time > current_time:
                temp_tasks.append(task)
                continue
            
            # Marquer comme programmée
            task.status = VisitStatus.SCHEDULED
            task.scheduled_time = current_time
            ready_tasks.append(task)
        
        # Remettre les tâches non prêtes dans le heap
        for task in temp_tasks:
            heapq.heappush(self._task_queue, task)
        
        return ready_tasks
    
    def _find_similar_task(self, target_bounds: GridBounds) -> Optional[ViewportTask]:
        """Trouve une tâche similaire existante"""
        for task in self._pending_tasks.values():
            if self._bounds_overlap(task.target_bounds, target_bounds):
                return task
        return None
    
    def _prune_low_priority_tasks(self) -> None:
        """Supprime les tâches de faible priorité pour faire de la place"""
        if len(self._pending_tasks) <= self.max_pending_tasks:
            return
        
        # Trier par priorité croissante
        sorted_tasks = sorted(self._pending_tasks.values(), key=lambda t: t.priority)
        
        # Supprimer les 20% les moins prioritaires
        to_remove = int(len(sorted_tasks) * 0.2)
        for task in sorted_tasks[:to_remove]:
            self._pending_tasks.pop(task.task_id, None)
            # Retirer du heap (reconstruction plus simple)
    
    def _cleanup_expired_tasks(self) -> None:
        """Nettoie les tâches expirées"""
        current_time = time.time()
        expired_tasks = []
        
        for task in self._pending_tasks.values():
            if (task.status == VisitStatus.IN_PROGRESS and 
                current_time - task.created_time > self.task_timeout):
                expired_tasks.append(task)
        
        for task in expired_tasks:
            self.complete_task(task.task_id, success=False, 
                             metadata={'reason': 'timeout'})
    
    def _enable_dependent_tasks(self, completed_task_id: str) -> None:
        """Active les tâches qui dépendent de la tâche complétée"""
        for task in self._pending_tasks.values():
            if completed_task_id in task.depends_on:
                task.depends_on.remove(completed_task_id)
                if not task.depends_on and task.status == VisitStatus.POSTPONED:
                    task.status = VisitStatus.PENDING
    
    def _dependencies_satisfied(self, task: ViewportTask) -> bool:
        """Vérifie si toutes les dépendances de la tâche sont satisfaites"""
        for dep_id in task.depends_on:
            if dep_id not in self._completed_tasks:
                return False
        return True
    
    def _calculate_distance_to_viewport(self, bounds: GridBounds, 
                                       viewport_bounds: GridBounds) -> float:
        """Calcule la distance entre une région et le viewport"""
        center_x = (bounds.x_min + bounds.x_max) // 2
        center_y = (bounds.y_min + bounds.y_max) // 2
        
        vp_center_x = (viewport_bounds.x_min + viewport_bounds.x_max) // 2
        vp_center_y = (viewport_bounds.y_min + viewport_bounds.y_max) // 2
        
        return math.sqrt((center_x - vp_center_x) ** 2 + (center_y - vp_center_y) ** 2)
    
    def _bounds_in_viewport(self, bounds: GridBounds, viewport_bounds: GridBounds) -> bool:
        """Vérifie si des bornes sont dans le viewport"""
        return not (bounds.x_max < viewport_bounds.x_min or 
                   bounds.x_min > viewport_bounds.x_max or
                   bounds.y_max < viewport_bounds.y_min or 
                   bounds.y_min > viewport_bounds.y_max)
    
    def _bounds_overlap(self, bounds1: GridBounds, bounds2: GridBounds) -> bool:
        """Vérifie si deux bornes se chevauchent"""
        return not (bounds1.x_max < bounds2.x_min or bounds1.x_min > bounds2.x_max or
                   bounds1.y_max < bounds2.y_min or bounds1.y_min > bounds2.y_max)
    
    def _update_duration_stats(self, duration: float) -> None:
        """Met à jour les statistiques de durée des tâches"""
        total_completed = self._stats['tasks_completed']
        current_avg = self._stats['average_task_duration']
        self._stats['average_task_duration'] = (
            (current_avg * (total_completed - 1) + duration) / total_completed
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de l'ordonnanceur"""
        with self._lock:
            stats = self._stats.copy()
            stats.update({
                'pending_tasks_count': len(self._pending_tasks),
                'completed_tasks_count': len(self._completed_tasks),
                'failed_tasks_count': len(self._failed_tasks),
                'capture_requests_count': len(self._capture_requests),
                'queue_length': len(self._task_queue)
            })
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'tasks_created': 0,
                'tasks_completed': 0,
                'tasks_failed': 0,
                'captures_triggered': 0,
                'average_task_duration': 0.0,
                'scheduling_efficiency': 0.0
            }
    
    def clear_all_tasks(self) -> None:
        """Efface toutes les tâches"""
        with self._lock:
            self._task_queue.clear()
            self._pending_tasks.clear()
            self._completed_tasks.clear()
            self._failed_tasks.clear()
            self._capture_requests.clear()
