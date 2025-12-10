"""
ActionExecutor - Exécuteur d'actions vers primitives S0 (S5.2)

Traduit les actions du solver en primitives de navigation:
- Conversion SolverAction → clic/flag/double-clic/scroll S0
- Interface avec S0 Navigation primitives
- Gestion des erreurs et retries
- Optimisation des séquences d'actions
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Protocol
from dataclasses import dataclass
from enum import Enum
import time
import threading
import math

from .s51_action_queue import QueuedAction, ActionStatus
from ..s4_solver.hybrid_solver import SolverAction
from ..s3_tensor.tensor_grid import TensorGrid, GridBounds, CellSymbol


# Interface S0 Navigation (stub pour l'instant)
class NavigationPrimitives(Protocol):
    """Interface pour les primitives de navigation S0"""
    
    def click_cell(self, x: int, y: int) -> bool:
        """Clic simple sur une cellule"""
        ...
    
    def flag_cell(self, x: int, y: int) -> bool:
        """Flag une cellule"""
        ...
    
    def double_click_cell(self, x: int, y: int) -> bool:
        """Double-clic sur une cellule (révélation rapide)"""
        ...
    
    def scroll_to(self, dx: int, dy: int) -> bool:
        """Scroll de la vue"""
        ...
    
    def get_current_viewport(self) -> GridBounds:
        """Retourne le viewport actuel"""
        ...


class ExecutionResult(Enum):
    """Résultats d'exécution d'action"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INVALID_COORDINATES = "invalid_coordinates"
    NAVIGATION_ERROR = "navigation_error"
    VERIFICATION_FAILED = "verification_failed"


@dataclass
class ExecutionReport:
    """Rapport d'exécution d'une action"""
    queue_id: str
    action: SolverAction
    result: ExecutionResult
    execution_time: float
    timestamp: float
    error_message: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ActionExecutor:
    """
    Exécuteur d'actions coordonnant S4 Solver → S0 Navigation
    
    Fonctionnalités:
    - Traduction des actions solver en primitives S0
    - Gestion des erreurs et retries automatiques
    - Vérification post-exécution
    - Optimisation des séquences d'actions
    """
    
    def __init__(self, tensor_grid: TensorGrid,
                 navigation_primitives: Optional[NavigationPrimitives] = None,
                 execution_timeout: float = 5.0,
                 max_retries: int = 3,
                 enable_verification: bool = True,
                 enable_action_optimization: bool = True):
        """
        Initialise l'exécuteur d'actions
        
        Args:
            tensor_grid: Grille tensorielle pour vérification
            navigation_primitives: Interface S0 Navigation (None = stub)
            execution_timeout: Timeout pour chaque action
            max_retries: Nombre maximum de retries par action
            enable_verification: Activer la vérification post-exécution
            enable_action_optimization: Activer l'optimisation des séquences
        """
        self._lock = threading.RLock()
        
        # Dépendances
        self.tensor_grid = tensor_grid
        self.navigation = navigation_primitives or self._create_stub_navigation()
        
        # Configuration
        self.execution_timeout = execution_timeout
        self.max_retries = max_retries
        self.enable_verification = enable_verification
        self.enable_action_optimization = enable_action_optimization
        
        # État d'exécution
        self._executing_actions: Dict[str, QueuedAction] = {}
        self._execution_history: List[ExecutionReport] = []
        
        # Optimisation
        self._action_sequence: List[SolverAction] = []
        self._sequence_cursor: int = 0
        
        # Statistiques
        self._stats = {
            'actions_executed': 0,
            'actions_successful': 0,
            'actions_failed': 0,
            'total_execution_time': 0.0,
            'average_execution_time': 0.0,
            'retry_rate': 0.0,
            'verification_failures': 0
        }
    
    def execute_action(self, queued_action: QueuedAction) -> ExecutionReport:
        """
        Exécute une action de la file
        
        Args:
            queued_action: Action à exécuter
            
        Returns:
            Rapport d'exécution détaillé
        """
        with self._lock:
            start_time = time.time()
            
            # Marquer comme en cours d'exécution
            self._executing_actions[queued_action.queue_id] = queued_action
            
            try:
                # Exécuter l'action
                result = self._execute_single_action(queued_action.action, queued_action.queue_id)
                
                # Vérifier le résultat si activé
                if self.enable_verification and result.result == ExecutionResult.SUCCESS:
                    verification_result = self._verify_action_result(queued_action.action)
                    if not verification_result:
                        result.result = ExecutionResult.VERIFICATION_FAILED
                        result.error_message = "Post-execution verification failed"
                        self._stats['verification_failures'] += 1
                
                # Mettre à jour les statistiques
                execution_time = time.time() - start_time
                self._update_execution_stats(result, execution_time)
                
                # Ajouter à l'historique
                self._execution_history.append(result)
                
                return result
                
            except Exception as e:
                # Erreur inattendue
                error_report = ExecutionReport(
                    queue_id=queued_action.queue_id,
                    action=queued_action.action,
                    result=ExecutionResult.FAILED,
                    execution_time=time.time() - start_time,
                    timestamp=time.time(),
                    error_message=f"Unexpected error: {str(e)}"
                )
                
                self._stats['actions_failed'] += 1
                self._execution_history.append(error_report)
                
                return error_report
                
            finally:
                # Nettoyer l'état d'exécution
                self._executing_actions.pop(queued_action.queue_id, None)
    
    def execute_action_sequence(self, actions: List[SolverAction]) -> List[ExecutionReport]:
        """
        Exécute une séquence optimisée d'actions
        
        Args:
            actions: Liste des actions à exécuter en séquence
            
        Returns:
            Liste des rapports d'exécution
        """
        with self._lock:
            if not actions:
                return []
            
            # Optimiser la séquence si activé
            optimized_actions = self._optimize_action_sequence(actions) if self.enable_action_optimization else actions
            
            reports = []
            
            for action in optimized_actions:
                # Créer une QueuedAction temporaire
                temp_queued = QueuedAction(
                    action=action,
                    queue_id=f"seq_{len(reports)}",
                    status=ActionStatus.EXECUTING,
                    created_time=time.time()
                )
                
                # Exécuter l'action
                report = self.execute_action(temp_queued)
                reports.append(report)
                
                # Arrêter si une action critique échoue
                if (report.result == ExecutionResult.FAILED and 
                    action.action_type in ['flag', 'reveal']):
                    break
            
            return reports
    
    def _execute_single_action(self, action: SolverAction, queue_id: str) -> ExecutionReport:
        """Exécute une action individuelle avec retries"""
        start_time = time.time()
        
        for attempt in range(self.max_retries + 1):
            try:
                # Traduire et exécuter l'action
                success = self._translate_and_execute(action)
                
                if success:
                    return ExecutionReport(
                        queue_id=queue_id,
                        action=action,
                        result=ExecutionResult.SUCCESS,
                        execution_time=time.time() - start_time,
                        timestamp=time.time(),
                        metadata={'attempt': attempt + 1}
                    )
                else:
                    # Échec, réessayer si possible
                    if attempt < self.max_retries:
                        time.sleep(0.1 * (attempt + 1))  # Backoff exponentiel
                        continue
                    else:
                        return ExecutionReport(
                            queue_id=queue_id,
                            action=action,
                            result=ExecutionResult.FAILED,
                            execution_time=time.time() - start_time,
                            timestamp=time.time(),
                            error_message=f"Failed after {self.max_retries + 1} attempts",
                            metadata={'attempt': attempt + 1}
                        )
                        
            except TimeoutError:
                if attempt < self.max_retries:
                    continue
                else:
                    return ExecutionReport(
                        queue_id=queue_id,
                        action=action,
                        result=ExecutionResult.TIMEOUT,
                        execution_time=time.time() - start_time,
                        timestamp=time.time(),
                        error_message="Execution timeout",
                        metadata={'attempt': attempt + 1}
                    )
                    
            except Exception as e:
                return ExecutionReport(
                    queue_id=queue_id,
                    action=action,
                    result=ExecutionResult.NAVIGATION_ERROR,
                    execution_time=time.time() - start_time,
                    timestamp=time.time(),
                    error_message=f"Navigation error: {str(e)}",
                    metadata={'attempt': attempt + 1}
                )
        
        # Ne devrait pas arriver
        return ExecutionReport(
            queue_id=queue_id,
            action=action,
            result=ExecutionResult.FAILED,
            execution_time=time.time() - start_time,
            timestamp=time.time(),
            error_message="Unexpected execution flow"
        )
    
    def _translate_and_execute(self, action: SolverAction) -> bool:
        """Traduit une action solver en primitive S0 et l'exécute"""
        x, y = action.coordinates
        
        # Validation des coordonnées
        if not self._validate_coordinates(x, y):
            raise ValueError(f"Invalid coordinates: ({x}, {y})")
        
        # Traduction selon le type d'action
        if action.action_type == 'reveal':
            return self.navigation.click_cell(x, y)
        elif action.action_type == 'flag':
            return self.navigation.flag_cell(x, y)
        elif action.action_type == 'guess':
            # Guess = clic avec faible confiance
            return self.navigation.click_cell(x, y)
        else:
            raise ValueError(f"Unknown action type: {action.action_type}")
    
    def _validate_coordinates(self, x: int, y: int) -> bool:
        """Valide les coordonnées d'une action"""
        # Vérifier si les coordonnées sont dans la vue solver
        solver_view = self.tensor_grid.get_solver_view()
        offset = solver_view['global_offset']
        height, width = solver_view['symbols'].shape
        
        local_x = x - offset[0]
        local_y = y - offset[1]
        
        return 0 <= local_x < width and 0 <= local_y < height
    
    def _verify_action_result(self, action: SolverAction) -> bool:
        """Vérifie qu'une action a eu l'effet attendu"""
        # Attendre un peu pour que l'interface se mette à jour
        time.sleep(0.1)
        
        # Obtenir l'état actuel
        solver_view = self.tensor_grid.get_solver_view()
        x, y = action.coordinates
        offset = solver_view['global_offset']
        local_x = x - offset[0]
        local_y = y - offset[1]
        
        current_symbol = solver_view['symbols'][local_y, local_x]
        
        # Vérification selon le type d'action
        if action.action_type == 'reveal':
            # La cellule ne devrait plus être inconnue
            return current_symbol != CellSymbol.UNKNOWN
        elif action.action_type == 'flag':
            # Pour un flag, on vérifie juste qu'il n'y a pas d'erreur
            # (la vérification visuelle des flags est complexe)
            return True
        elif action.action_type == 'guess':
            # Guess réussi si la cellule a changé
            return current_symbol != CellSymbol.UNKNOWN
        
        return True
    
    def _optimize_action_sequence(self, actions: List[SolverAction]) -> List[SolverAction]:
        """Optimise l'ordre d'exécution d'une séquence d'actions"""
        if len(actions) <= 1:
            return actions
        
        # Séparer par type
        flag_actions = [a for a in actions if a.action_type == 'flag']
        reveal_actions = [a for a in actions if a.action_type == 'reveal']
        guess_actions = [a for a in actions if a.action_type == 'guess']
        
        # Optimiser l'ordre spatial pour chaque type
        flag_actions = self._optimize_spatial_order(flag_actions)
        reveal_actions = self._optimize_spatial_order(reveal_actions)
        guess_actions = self._optimize_spatial_order(guess_actions)
        
        # Ordre: flags d'abord, puis reveals, puis guesses
        return flag_actions + reveal_actions + guess_actions
    
    def _optimize_spatial_order(self, actions: List[SolverAction]) -> List[SolverAction]:
        """Optimise l'ordre spatial pour minimiser les mouvements"""
        if len(actions) <= 1:
            return actions
        
        # Algorithme du plus proche voisin (TSP simplifié)
        optimized = []
        remaining = actions.copy()
        
        # Commencer par l'action la plus confidente
        current = max(remaining, key=lambda a: a.confidence)
        remaining.remove(current)
        optimized.append(current)
        
        while remaining:
            # Trouver l'action la plus proche de la position actuelle
            current_pos = current.coordinates
            nearest = min(remaining, 
                         key=lambda a: math.sqrt((a.coordinates[0] - current_pos[0]) ** 2 + 
                                               (a.coordinates[1] - current_pos[1]) ** 2))
            
            remaining.remove(nearest)
            optimized.append(nearest)
            current = nearest
        
        return optimized
    
    def _create_stub_navigation(self) -> NavigationPrimitives:
        """Crée un stub de navigation pour les tests"""
        class StubNavigation:
            def __init__(self):
                self.call_log = []
            
            def click_cell(self, x: int, y: int) -> bool:
                self.call_log.append(('click', x, y))
                return True
            
            def flag_cell(self, x: int, y: int) -> bool:
                self.call_log.append(('flag', x, y))
                return True
            
            def double_click_cell(self, x: int, y: int) -> bool:
                self.call_log.append(('double_click', x, y))
                return True
            
            def scroll_to(self, dx: int, dy: int) -> bool:
                self.call_log.append(('scroll', dx, dy))
                return True
            
            def get_current_viewport(self) -> GridBounds:
                return GridBounds(0, 0, 800, 600)
        
        return StubNavigation()
    
    def _update_execution_stats(self, report: ExecutionReport, execution_time: float) -> None:
        """Met à jour les statistiques d'exécution"""
        self._stats['actions_executed'] += 1
        
        if report.result == ExecutionResult.SUCCESS:
            self._stats['actions_successful'] += 1
        else:
            self._stats['actions_failed'] += 1
        
        # Mettre à jour le temps moyen
        total_executed = self._stats['actions_executed']
        current_avg = self._stats['average_execution_time']
        self._stats['average_execution_time'] = (
            (current_avg * (total_executed - 1) + execution_time) / total_executed
        )
        
        self._stats['total_execution_time'] += execution_time
        
        # Calculer le taux de retry
        attempts = report.metadata.get('attempt', 1) if report.metadata else 1
        if attempts > 1:
            current_retry_rate = self._stats['retry_rate']
            self._stats['retry_rate'] = (
                (current_retry_rate * (total_executed - 1) + (attempts - 1)) / total_executed
            )
    
    def get_execution_status(self) -> Dict[str, Any]:
        """Retourne le statut actuel de l'exécution"""
        with self._lock:
            return {
                'executing_actions': len(self._executing_actions),
                'execution_history_size': len(self._execution_history),
                'current_success_rate': (
                    self._stats['actions_successful'] / max(1, self._stats['actions_executed'])
                )
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de l'exécuteur"""
        with self._lock:
            stats = self._stats.copy()
            stats.update(self.get_execution_status())
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'actions_executed': 0,
                'actions_successful': 0,
                'actions_failed': 0,
                'total_execution_time': 0.0,
                'average_execution_time': 0.0,
                'retry_rate': 0.0,
                'verification_failures': 0
            }
            self._execution_history.clear()
    
    def get_recent_reports(self, count: int = 10) -> List[ExecutionReport]:
        """Retourne les rapports d'exécution récents"""
        with self._lock:
            return self._execution_history[-count:] if self._execution_history else []
