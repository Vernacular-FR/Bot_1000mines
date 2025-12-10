"""
ActionQueue - File d'attente et ordonnancement des actions (S5.1)

Gère les actions validées par le solver:
- File prioritaire ordonnée des actions solver
- Déduplication des actions redondantes
- Optimisation de l'ordre pour minimiser les mouvements
- Interface avec S4 HybridSolver et S5 ActionExecutor
"""

import numpy as np
import heapq
import math
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
import hashlib
from collections import defaultdict, deque

from ..s4_solver.hybrid_solver import SolverAction, SolverResult
from ..s3_tensor.tensor_grid import TensorGrid, GridBounds, CellSymbol


class ActionStatus(Enum):
    """Statuts des actions dans la file"""
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionPriority(Enum):
    """Priorités des actions"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class QueuedAction:
    """Action dans la file avec métadonnées"""
    action: SolverAction
    queue_id: str
    status: ActionStatus
    created_time: float
    scheduled_time: Optional[float] = None
    execution_start: Optional[float] = None
    completion_time: Optional[float] = None
    
    # Métadonnées d'ordonnancement
    priority: ActionPriority = ActionPriority.MEDIUM
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    
    # Optimisation
    cluster_id: Optional[str] = None
    execution_order: int = 0
    
    def __hash__(self):
        return hash(self.queue_id)
    
    def __eq__(self, other):
        return self.queue_id == other.queue_id
    
    def __lt__(self, other):
        """Pour le tri par priorité"""
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value  # Ordre décroissant
        return self.created_time < other.created_time  # Plus ancien d'abord


@dataclass
class ActionCluster:
    """Cluster d'actions spatialement proches"""
    cluster_id: str
    actions: List[QueuedAction]
    center: Tuple[int, int]
    bounds: GridBounds
    total_priority: float
    
    def get_optimal_order(self) -> List[QueuedAction]:
        """Retourne l'ordre optimal d'exécution pour minimiser les mouvements"""
        if len(self.actions) <= 1:
            return self.actions
        
        # Trier par distance au centre (spirale)
        sorted_actions = sorted(
            self.actions,
            key=lambda a: math.sqrt(
                (a.action.coordinates[0] - self.center[0]) ** 2 +
                (a.action.coordinates[1] - self.center[1]) ** 2
            )
        )
        
        # Regrouper par type d'action pour optimiser
        reveal_actions = [a for a in sorted_actions if a.action.action_type == 'reveal']
        flag_actions = [a for a in sorted_actions if a.action.action_type == 'flag']
        
        # Ordre: flags d'abord, puis reveals (évite de révéler des mines qu'on voulait flagger)
        return flag_actions + reveal_actions


class ActionQueue:
    """
    File d'attente intelligente pour les actions du solver
    
    Fonctionnalités:
    - File prioritaire avec déduplication
    - Clustering spatial pour optimiser les mouvements
    - Gestion des dépendances entre actions
    - Optimisation de l'ordre d'exécution
    """
    
    def __init__(self, tensor_grid: TensorGrid,
                 max_queue_size: int = 100,
                 enable_clustering: bool = True,
                 cluster_radius: int = 30,
                 enable_deduplication: bool = True):
        """
        Initialise la file d'actions
        
        Args:
            tensor_grid: Grille tensorielle pour vérifier l'état
            max_queue_size: Taille maximale de la file
            enable_clustering: Activer le clustering spatial
            cluster_radius: Rayon pour le clustering (pixels)
            enable_deduplication: Activer la déduplication
        """
        self._lock = threading.RLock()
        
        # Dépendances
        self.tensor_grid = tensor_grid
        
        # Configuration
        self.max_queue_size = max_queue_size
        self.enable_clustering = enable_clustering
        self.cluster_radius = cluster_radius
        self.enable_deduplication = enable_deduplication
        
        # Files et états
        self._action_heap: List[QueuedAction] = []  # Heap de priorité
        self._queued_actions: Dict[str, QueuedAction] = {}  # Accès rapide
        self._action_history: List[QueuedAction] = []  # Historique
        
        # Clustering
        self._clusters: Dict[str, ActionCluster] = {}
        self._coordinate_index: Dict[Tuple[int, int], List[str]] = defaultdict(list)
        
        # Compteurs
        self._action_counter: int = 0
        
        # Statistiques
        self._stats = {
            'actions_queued': 0,
            'actions_executed': 0,
            'actions_failed': 0,
            'duplicates_removed': 0,
            'clusters_created': 0,
            'average_queue_time': 0.0,
            'optimization_efficiency': 0.0
        }
    
    def enqueue_solver_result(self, solver_result: SolverResult) -> List[str]:
        """
        Ajoute les actions d'un résultat solver à la file
        
        Args:
            solver_result: Résultat du solver avec actions
            
        Returns:
            Liste des IDs des actions ajoutées
        """
        with self._lock:
            action_ids = []
            
            # Filtrer et valider les actions
            valid_actions = self._filter_valid_actions(solver_result.actions)
            
            # Ajouter chaque action
            for action in valid_actions:
                action_id = self._enqueue_single_action(action)
                if action_id:
                    action_ids.append(action_id)
            
            # Optimiser la file si clustering activé
            if self.enable_clustering and len(action_ids) > 1:
                self._update_clusters()
            
            return action_ids
    
    def _enqueue_single_action(self, action: SolverAction) -> Optional[str]:
        """Ajoute une action individuelle à la file"""
        # Vérifier la taille de la file
        if len(self._queued_actions) >= self.max_queue_size:
            self._prune_low_priority_actions()
        
        # Déduplication si activée
        if self.enable_deduplication:
            existing_id = self._find_duplicate_action(action)
            if existing_id:
                self._stats['duplicates_removed'] += 1
                return existing_id
        
        # Créer l'entrée dans la file
        queue_id = f"action_{self._action_counter}"
        self._action_counter += 1
        
        # Calculer la priorité
        priority = self._calculate_action_priority(action)
        
        queued_action = QueuedAction(
            action=action,
            queue_id=queue_id,
            status=ActionStatus.QUEUED,
            created_time=time.time(),
            priority=priority
        )
        
        # Ajouter aux structures
        self._queued_actions[queue_id] = queued_action
        self._coordinate_index[action.coordinates].append(queue_id)
        
        # Mettre à jour les statistiques
        self._stats['actions_queued'] += 1
        
        return queue_id
    
    def _filter_valid_actions(self, actions: List[SolverAction]) -> List[SolverAction]:
        """Filtre les actions valides selon l'état actuel de TensorGrid"""
        valid_actions = []
        solver_view = self.tensor_grid.get_solver_view()
        
        for action in actions:
            x, y = action.coordinates
            
            # Vérifier si les coordonnées sont dans la grille
            if not self._is_in_solver_view(x, y, solver_view):
                continue
            
            # Vérifier si l'action est encore pertinente
            if not self._is_action_still_relevant(action, solver_view):
                continue
            
            valid_actions.append(action)
        
        return valid_actions
    
    def _is_in_solver_view(self, x: int, y: int, solver_view: Dict[str, Any]) -> bool:
        """Vérifie si les coordonnées sont dans la vue solver"""
        offset = solver_view['global_offset']
        height, width = solver_view['symbols'].shape
        
        local_x = x - offset[0]
        local_y = y - offset[1]
        
        return 0 <= local_x < width and 0 <= local_y < height
    
    def _is_action_still_relevant(self, action: SolverAction, 
                                 solver_view: Dict[str, Any]) -> bool:
        """Vérifie si l'action est encore pertinente selon l'état actuel"""
        x, y = action.coordinates
        offset = solver_view['global_offset']
        local_x = x - offset[0]
        local_y = y - offset[1]
        
        symbol = solver_view['symbols'][local_y, local_x]
        
        if action.action_type == 'reveal':
            # Ne révéler que les cellules inconnues
            return symbol == CellSymbol.UNKNOWN
        elif action.action_type == 'flag':
            # Ne flagger que les cellules inconnues ou non flaggées
            return symbol == CellSymbol.UNKNOWN
        elif action.action_type == 'guess':
            # Deviner seulement les inconnues
            return symbol == CellSymbol.UNKNOWN
        
        return False
    
    def _find_duplicate_action(self, action: SolverAction) -> Optional[str]:
        """Trouve une action dupliquée existante"""
        coordinates = action.coordinates
        
        for queue_id in self._coordinate_index[coordinates]:
            queued_action = self._queued_actions.get(queue_id)
            if queued_action and queued_action.action.action_type == action.action_type:
                return queue_id
        
        return None
    
    def _calculate_action_priority(self, action: SolverAction) -> ActionPriority:
        """Calcule la priorité d'une action"""
        base_priority = action.confidence
        
        # Ajuster selon le type d'action
        if action.action_type == 'flag':
            # Les flags sont critiques (éviter de cliquer sur des mines)
            priority_multiplier = 1.2
        elif action.action_type == 'reveal':
            # Les révélations sont importantes
            priority_multiplier = 1.0
        elif action.action_type == 'guess':
            # Les guesses sont moins prioritaires
            priority_multiplier = 0.7
        else:
            priority_multiplier = 1.0
        
        adjusted_priority = base_priority * priority_multiplier
        
        # Convertir en enum
        if adjusted_priority > 0.9:
            return ActionPriority.CRITICAL
        elif adjusted_priority > 0.7:
            return ActionPriority.HIGH
        elif adjusted_priority > 0.4:
            return ActionPriority.MEDIUM
        else:
            return ActionPriority.LOW
    
    def _update_clusters(self) -> None:
        """Met à jour les clusters d'actions spatiales"""
        # Nettoyer les anciens clusters
        self._clusters.clear()
        
        # Regrouper les actions par proximité spatiale
        unclustered_actions = list(self._queued_actions.values())
        
        while unclustered_actions:
            # Prendre la première action comme centre de cluster
            center_action = unclustered_actions.pop(0)
            center_coords = center_action.action.coordinates
            
            # Trouver les actions proches
            cluster_actions = [center_action]
            remaining_actions = []
            
            for action in unclustered_actions:
                dist = math.sqrt(
                    (action.action.coordinates[0] - center_coords[0]) ** 2 +
                    (action.action.coordinates[1] - center_coords[1]) ** 2
                )
                
                if dist <= self.cluster_radius:
                    cluster_actions.append(action)
                else:
                    remaining_actions.append(action)
            
            unclustered_actions = remaining_actions
            
            # Créer le cluster
            if len(cluster_actions) > 1:
                cluster_id = f"cluster_{len(self._clusters)}"
                cluster = self._create_cluster(cluster_id, cluster_actions)
                self._clusters[cluster_id] = cluster
                
                # Assigner le cluster aux actions
                for action in cluster_actions:
                    action.cluster_id = cluster_id
                
                self._stats['clusters_created'] += 1
    
    def _create_cluster(self, cluster_id: str, actions: List[QueuedAction]) -> ActionCluster:
        """Crée un cluster d'actions"""
        # Calculer le centre
        coords = [a.action.coordinates for a in actions]
        center_x = sum(c[0] for c in coords) / len(coords)
        center_y = sum(c[1] for c in coords) / len(coords)
        
        # Calculer les bornes
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        
        bounds = GridBounds(
            x_min=min(xs), y_min=min(ys),
            x_max=max(xs), y_max=max(ys)
        )
        
        # Calculer la priorité totale
        total_priority = sum(a.priority.value for a in actions)
        
        return ActionCluster(
            cluster_id=cluster_id,
            actions=actions,
            center=(int(center_x), int(center_y)),
            bounds=bounds,
            total_priority=total_priority
        )
    
    def get_next_actions(self, max_count: int = 5) -> List[QueuedAction]:
        """
        Retourne les prochaines actions à exécuter
        
        Args:
            max_count: Nombre maximum d'actions
            
        Returns:
            Liste des actions prêtes à être exécutées
        """
        with self._lock:
            # Reconstruire le heap avec les priorités actuelles
            self._rebuild_heap()
            
            # Extraire les actions prêtes
            ready_actions = []
            
            while self._action_heap and len(ready_actions) < max_count:
                action = heapq.heappop(self._action_heap)
                
                # Vérifier si l'action est toujours valide
                if action.queue_id not in self._queued_actions:
                    continue
                
                # Vérifier si l'action est encore pertinente
                if not self._is_action_still_relevant(action.action, 
                                                     self.tensor_grid.get_solver_view()):
                    self._remove_action(action.queue_id)
                    continue
                
                # Marquer comme programmée
                action.status = ActionStatus.SCHEDULED
                action.scheduled_time = time.time()
                ready_actions.append(action)
            
            return ready_actions
    
    def _rebuild_heap(self) -> None:
        """Reconstruit le heap de priorité"""
        self._action_heap = list(self._queued_actions.values())
        heapq.heapify(self._action_heap)
    
    def _prune_low_priority_actions(self) -> None:
        """Supprime les actions de faible priorité pour faire de la place"""
        if len(self._queued_actions) <= self.max_queue_size:
            return
        
        # Trier par priorité croissante
        sorted_actions = sorted(self._queued_actions.values(), 
                              key=lambda a: a.priority.value)
        
        # Supprimer les 20% les moins prioritaires
        to_remove = int(len(sorted_actions) * 0.2)
        for action in sorted_actions[:to_remove]:
            self._remove_action(action.queue_id)
    
    def mark_action_executing(self, queue_id: str) -> bool:
        """Marque une action comme en cours d'exécution"""
        with self._lock:
            action = self._queued_actions.get(queue_id)
            if action:
                action.status = ActionStatus.EXECUTING
                action.execution_start = time.time()
                return True
            return False
    
    def complete_action(self, queue_id: str, success: bool = True, 
                       metadata: Dict[str, Any] = None) -> None:
        """
        Marque une action comme complétée
        
        Args:
            queue_id: ID de l'action
            success: True si succès, False si échec
            metadata: Métadonnées du résultat
        """
        with self._lock:
            action = self._queued_actions.get(queue_id)
            if not action:
                return
            
            action.completion_time = time.time()
            
            if success:
                action.status = ActionStatus.COMPLETED
                self._stats['actions_executed'] += 1
            else:
                action.status = ActionStatus.FAILED
                self._stats['actions_failed'] += 1
            
            # Calculer le temps d'attente
            if action.scheduled_time:
                queue_time = action.scheduled_time - action.created_time
                self._update_queue_time_stats(queue_time)
            
            # Retirer de la file active
            self._remove_action(queue_id)
            
            # Ajouter à l'historique
            self._action_history.append(action)
            
            # Limiter l'historique
            if len(self._action_history) > 1000:
                self._action_history = self._action_history[-500:]
    
    def _remove_action(self, queue_id: str) -> None:
        """Retire une action de la file active"""
        action = self._queued_actions.pop(queue_id, None)
        if action:
            # Retirer de l'index spatial
            coords = action.action.coordinates
            if queue_id in self._coordinate_index[coords]:
                self._coordinate_index[coords].remove(queue_id)
            
            # Retirer du cluster
            if action.cluster_id and action.cluster_id in self._clusters:
                cluster = self._clusters[action.cluster_id]
                cluster.actions = [a for a in cluster.actions if a.queue_id != queue_id]
                
                # Supprimer le cluster s'il est vide
                if not cluster.actions:
                    del self._clusters[action.cluster_id]
    
    def _update_queue_time_stats(self, queue_time: float) -> None:
        """Met à jour les statistiques de temps d'attente"""
        total_executed = self._stats['actions_executed']
        current_avg = self._stats['average_queue_time']
        self._stats['average_queue_time'] = (
            (current_avg * (total_executed - 1) + queue_time) / total_executed
        )
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Retourne le statut actuel de la file"""
        with self._lock:
            status_counts = defaultdict(int)
            for action in self._queued_actions.values():
                status_counts[action.status.value] += 1
            
            return {
                'total_queued': len(self._queued_actions),
                'by_status': dict(status_counts),
                'clusters_count': len(self._clusters),
                'average_priority': np.mean([a.priority.value for a in self._queued_actions.values()]) if self._queued_actions else 0.0
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de la file"""
        with self._lock:
            stats = self._stats.copy()
            stats.update({
                'current_queue_size': len(self._queued_actions),
                'history_size': len(self._action_history),
                'active_clusters': len(self._clusters)
            })
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'actions_queued': 0,
                'actions_executed': 0,
                'actions_failed': 0,
                'duplicates_removed': 0,
                'clusters_created': 0,
                'average_queue_time': 0.0,
                'optimization_efficiency': 0.0
            }
    
    def clear_queue(self) -> None:
        """Vide toute la file d'attente"""
        with self._lock:
            self._action_heap.clear()
            self._queued_actions.clear()
            self._clusters.clear()
            self._coordinate_index.clear()
