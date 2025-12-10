"""
CaptureTrigger - Déclenchement intelligent des captures (S1.1)

Gère le déclenchement des captures d'écran basé sur les confirmations S0:
- Déclenchement sur confirmation d'action S0
- Gestion des taux de capture et optimisation
- Intégration avec S0 Navigation primitives
- Support pour les captures périodiques et événementielles
"""

import time
import threading
from typing import Optional, Callable, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

from ..s0_navigation.s01_primitives import BrowserNavigation, ActionResult
from ..s0_navigation.s03_coordinate_converter import CoordinateConverter


class TriggerType(Enum):
    """Types de déclencheurs de capture"""
    ACTION_CONFIRMATION = "action_confirmation"  # Après confirmation S0
    PERIODIC = "periodic"                         # Capture périodique
    VIEWPORT_CHANGE = "viewport_change"           # Changement de viewport
    MANUAL = "manual"                             # Déclenchement manuel
    ERROR_RECOVERY = "error_recovery"             # Après erreur S0
    DENSITY_REQUEST = "density_request"           # Demande S6 Pathfinder


@dataclass
class CaptureRequest:
    """Requête de capture d'écran"""
    request_id: str
    trigger_type: TriggerType
    timestamp: float
    priority: int  # 1=low, 5=high
    metadata: Dict[str, Any]
    
    # Contexte de la capture
    action_coordinates: Optional[tuple] = None
    viewport_bounds: Optional[tuple] = None
    expected_changes: bool = False  # Si des changements sont attendus


@dataclass
class CaptureResult:
    """Résultat d'une capture d'écran"""
    request_id: str
    success: bool
    timestamp: float
    screenshot_data: Optional[np.ndarray] = None
    capture_time: float = 0.0
    error_message: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class CaptureTrigger:
    """
    Gestionnaire de déclenchement des captures
    
    Fonctionnalités:
    - Déclenchement intelligent basé sur les événements S0
    - Gestion des priorités et taux de capture
    - Intégration avec S0 Navigation
    - Optimisation des performances de capture
    """
    
    def __init__(self, navigation: BrowserNavigation,
                 coordinate_converter: Optional[CoordinateConverter] = None,
                 max_capture_rate: float = 10.0,  # captures par seconde
                 enable_periodic_capture: bool = False,
                 periodic_interval: float = 1.0,
                 capture_timeout: float = 5.0):
        """
        Initialise le déclencheur de captures
        
        Args:
            navigation: Instance de navigation S0
            max_capture_rate: Taux maximum de captures/seconde
            enable_periodic_capture: Activer les captures périodiques
            periodic_interval: Intervalle des captures périodiques
            capture_timeout: Timeout pour les captures
        """
        # Dépendances
        self.navigation = navigation
        self.coordinate_converter = coordinate_converter
        
        # Configuration
        self.max_capture_rate = max_capture_rate
        self.enable_periodic_capture = enable_periodic_capture
        self.periodic_interval = periodic_interval
        self.capture_timeout = capture_timeout
        self.min_capture_interval = 1.0 / max_capture_rate
        
        # État des captures
        self._lock = threading.RLock()
        self._capture_queue: List[CaptureRequest] = []
        self._pending_requests: Dict[str, CaptureRequest] = {}
        self._capture_callbacks: List[Callable[[CaptureResult], None]] = []
        
        # Contrôle des taux
        self._last_capture_time: float = 0.0
        self._capture_count: int = 0
        self._capture_times: List[float] = []
        
        # Thread de capture périodique
        self._periodic_thread: Optional[threading.Thread] = None
        self._stop_periodic = threading.Event()
        
        # Compteurs
        self._request_counter: int = 0
        
        # Statistiques
        self._stats = {
            'total_requests': 0,
            'successful_captures': 0,
            'failed_captures': 0,
            'average_capture_time': 0.0,
            'current_capture_rate': 0.0,
            'queue_size': 0
        }
        
        # Démarrer les captures périodiques si activées
        if self.enable_periodic_capture:
            self._start_periodic_capture()

    # ------------------------------------------------------------------ #
    # Captures directes (legacy "capture_between_cells")
    # ------------------------------------------------------------------ #
    def capture_between_cells(
        self,
        cell1: Tuple[int, int],
        cell2: Tuple[int, int],
        *,
        add_margin: bool = True,
        margin_cells: int = 1,
        coordinate_converter: Optional[CoordinateConverter] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CaptureResult:
        """
        Capture directe d'une zone entre deux cases de la grille.

        Args:
            cell1: Coordonnées (x, y) de la première case.
            cell2: Coordonnées (x, y) de la seconde case.
            add_margin: Ajoute une marge (en cases) autour de la zone.
            margin_cells: Taille de la marge en nombre de cases.
            coordinate_converter: Convertisseur explicite (fallback sur self.coordinate_converter).
            metadata: Métadonnées additionnelles à propager.
        """
        converter = coordinate_converter or self.coordinate_converter
        if converter is None:
            return CaptureResult(
                request_id="direct_invalid_converter",
                success=False,
                timestamp=time.time(),
                error_message="CoordinateConverter requis pour capture_between_cells",
                metadata=metadata or {},
            )

        request_id = self._next_direct_request_id(prefix="direct_cells")

        try:
            px1, py1 = converter.grid_to_screen(*cell1)
            px2, py2 = converter.grid_to_screen(*cell2)
        except Exception as err:
            return CaptureResult(
                request_id=request_id,
                success=False,
                timestamp=time.time(),
                error_message=f"Conversion coordonnées impossible: {err}",
                metadata=metadata or {},
            )

        cell_margin = margin_cells * converter.get_effective_cell_size() if add_margin else 0
        x_min = min(px1, px2) - cell_margin
        y_min = min(py1, py2) - cell_margin
        x_max = max(px1, px2) + cell_margin
        y_max = max(py1, py2) + cell_margin

        screenshot_bytes = self.navigation.take_screenshot()
        if screenshot_bytes is None:
            return CaptureResult(
                request_id=request_id,
                success=False,
                timestamp=time.time(),
                error_message="Impossible de capturer le screenshot navigateur",
                metadata=metadata or {},
            )

        import io
        from PIL import Image

        start_time = time.time()
        with Image.open(io.BytesIO(screenshot_bytes)) as img:
            width, height = img.size
            crop_box = (
                max(0, int(x_min)),
                max(0, int(y_min)),
                min(width, int(x_max)),
                min(height, int(y_max)),
            )

            if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                return CaptureResult(
                    request_id=request_id,
                    success=False,
                    timestamp=time.time(),
                    error_message="Zone de capture invalide (dimensions nulles)",
                    metadata=metadata or {},
                )

            zone_image = img.crop(crop_box)
            screenshot_array = np.array(zone_image)

        capture_metadata = {
            "capture_type": "between_cells",
            "cell1": cell1,
            "cell2": cell2,
            "margin_cells": margin_cells if add_margin else 0,
            "cell_size_px": converter.get_effective_cell_size(),
            "bounds_px": {
                "x_min": crop_box[0],
                "y_min": crop_box[1],
                "x_max": crop_box[2],
                "y_max": crop_box[3],
            },
            "screen_width": width,
            "screen_height": height,
        }
        if metadata:
            capture_metadata.update(metadata)

        result = CaptureResult(
            request_id=request_id,
            success=True,
            timestamp=time.time(),
            screenshot_data=screenshot_array,
            capture_time=time.time() - start_time,
            metadata=capture_metadata,
        )
        self._update_capture_stats(True, result.capture_time)
        return result
    
    def trigger_capture_on_action(self, action_type: str, coordinates: tuple,
                                 success: bool, action_result: ActionResult) -> str:
        """
        Déclenche une capture après une action S0
        
        Args:
            action_type: Type d'action ('click', 'flag', 'double_click')
            coordinates: Coordonnées de l'action
            success: Si l'action a réussi
            action_result: Résultat détaillé de l'action
            
        Returns:
            ID de la requête de capture
        """
        # Déterminer la priorité basée sur le type d'action
        priority = self._calculate_action_priority(action_type, success)
        
        # Créer la requête
        request = CaptureRequest(
            request_id=f"action_{self._request_counter}",
            trigger_type=TriggerType.ACTION_CONFIRMATION,
            timestamp=time.time(),
            priority=priority,
            metadata={
                'action_type': action_type,
                'action_success': success,
                'action_result': action_result.value
            },
            action_coordinates=coordinates,
            expected_changes=True  # On s'attend à des changements après une action
        )
        
        return self._submit_request(request)
    
    def trigger_manual_capture(self, priority: int = 3,
                              viewport_bounds: Optional[tuple] = None) -> str:
        """
        Déclenche une capture manuelle
        
        Args:
            priority: Priorité de la capture (1-5)
            viewport_bounds: Bornes du viewport à capturer
            
        Returns:
            ID de la requête de capture
        """
        request = CaptureRequest(
            request_id=f"manual_{self._request_counter}",
            trigger_type=TriggerType.MANUAL,
            timestamp=time.time(),
            priority=priority,
            metadata={'manual_trigger': True},
            viewport_bounds=viewport_bounds,
            expected_changes=False
        )
        
        return self._submit_request(request)
    
    def trigger_density_capture(self, region_bounds: tuple,
                               priority: int = 4) -> str:
        """
        Déclenche une capture pour analyse de densité (S6)
        
        Args:
            region_bounds: Bornes de la région d'intérêt
            priority: Priorité de la capture
            
        Returns:
            ID de la requête de capture
        """
        request = CaptureRequest(
            request_id=f"density_{self._request_counter}",
            trigger_type=TriggerType.DENSITY_REQUEST,
            timestamp=time.time(),
            priority=priority,
            metadata={
                'density_analysis': True,
                'region_bounds': region_bounds
            },
            viewport_bounds=region_bounds,
            expected_changes=False
        )
        
        return self._submit_request(request)
    
    def trigger_error_recovery_capture(self, error_context: Dict[str, Any]) -> str:
        """
        Déclenche une capture pour récupération d'erreur
        
        Args:
            error_context: Contexte de l'erreur
            
        Returns:
            ID de la requête de capture
        """
        request = CaptureRequest(
            request_id=f"error_{self._request_counter}",
            trigger_type=TriggerType.ERROR_RECOVERY,
            timestamp=time.time(),
            priority=5,  # Haute priorité pour les erreurs
            metadata={'error_context': error_context},
            expected_changes=False
        )
        
        return self._submit_request(request)
    
    def process_capture_queue(self) -> List[CaptureResult]:
        """
        Traite la file des captures en attente
        
        Returns:
            Liste des résultats de capture
        """
        with self._lock:
            if not self._capture_queue:
                return []
            
            results = []
            
            # Trier par priorité
            sorted_requests = sorted(self._capture_queue, 
                                   key=lambda r: r.priority, reverse=True)
            
            # Traiter les requêtes en respectant le taux limite
            for request in sorted_requests:
                if self._should_capture_now():
                    result = self._execute_capture(request)
                    results.append(result)
                    
                    # Retirer de la file
                    self._capture_queue.remove(request)
                    self._pending_requests.pop(request.request_id, None)
                    
                    # Notifier les callbacks
                    self._notify_callbacks(result)
                else:
                    # Attendre avant la prochaine capture
                    break
            
            return results
    
    def register_capture_callback(self, callback: Callable[[CaptureResult], None]) -> None:
        """
        Enregistre un callback pour les résultats de capture
        
        Args:
            callback: Fonction appelée après chaque capture
        """
        with self._lock:
            self._capture_callbacks.append(callback)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Retourne le statut de la file de captures"""
        with self._lock:
            return {
                'queue_size': len(self._capture_queue),
                'pending_requests': len(self._pending_requests),
                'last_capture_age': time.time() - self._last_capture_time,
                'current_rate': self._calculate_current_rate(),
                'requests_by_priority': self._count_by_priority()
            }
    
    def _submit_request(self, request: CaptureRequest) -> str:
        """Soumet une requête de capture"""
        with self._lock:
            self._request_counter += 1
            
            # Ajouter à la file
            self._capture_queue.append(request)
            self._pending_requests[request.request_id] = request
            
            # Mettre à jour les statistiques
            self._stats['total_requests'] += 1
            self._stats['queue_size'] = len(self._capture_queue)
            
            return request.request_id
    
    def _should_capture_now(self) -> bool:
        """Vérifie si une capture peut être effectuée maintenant"""
        current_time = time.time()
        time_since_last = current_time - self._last_capture_time
        
        return time_since_last >= self.min_capture_interval
    
    def _execute_capture(self, request: CaptureRequest) -> CaptureResult:
        """Exécute une capture d'écran"""
        start_time = time.time()
        
        try:
            # Prendre la capture via S0 Navigation
            screenshot_data = self.navigation.take_screenshot()
            
            if screenshot_data is None:
                raise RuntimeError("Failed to capture screenshot")
            
            # Convertir en numpy array
            import io
            from PIL import Image
            
            image = Image.open(io.BytesIO(screenshot_data))
            screenshot_array = np.array(image)
            
            # Créer le résultat
            result = CaptureResult(
                request_id=request.request_id,
                success=True,
                timestamp=time.time(),
                screenshot_data=screenshot_array,
                capture_time=time.time() - start_time,
                metadata=request.metadata.copy()
            )
            
            # Mettre à jour les statistiques
            self._update_capture_stats(True, result.capture_time)
            
            return result
            
        except Exception as e:
            # Capture échouée
            result = CaptureResult(
                request_id=request.request_id,
                success=False,
                timestamp=time.time(),
                capture_time=time.time() - start_time,
                error_message=str(e)
            )
            
            # Mettre à jour les statistiques
            self._update_capture_stats(False, result.capture_time)
            
            return result
    
    def _calculate_action_priority(self, action_type: str, success: bool) -> int:
        """Calcule la priorité basée sur le type d'action"""
        base_priorities = {
            'click': 3,
            'flag': 4,  # Les flags sont plus importants
            'double_click': 3,
            'scroll': 2
        }
        
        priority = base_priorities.get(action_type, 3)
        
        # Ajuster selon le succès
        if not success:
            priority += 1  # Priorité plus haute après un échec
        
        return min(5, priority)  # Limiter à 5
    
    def _update_capture_stats(self, success: bool, capture_time: float) -> None:
        """Met à jour les statistiques de capture"""
        self._last_capture_time = time.time()
        self._capture_count += 1
        
        # Enregistrer le temps
        self._capture_times.append(capture_time)
        if len(self._capture_times) > 100:
            self._capture_times = self._capture_times[-100:]
        
        # Mettre à jour les statistiques
        if success:
            self._stats['successful_captures'] += 1
        else:
            self._stats['failed_captures'] += 1
        
        self._stats['average_capture_time'] = (
            sum(self._capture_times) / len(self._capture_times)
        )
        self._stats['current_capture_rate'] = self._calculate_current_rate()
    
    def _calculate_current_rate(self) -> float:
        """Calcule le taux de capture actuel"""
        if len(self._capture_times) < 2:
            return 0.0
        
        # Utiliser les 10 dernières captures
        recent_times = self._capture_times[-10:]
        average_time = sum(recent_times) / len(recent_times)
        
        return 1.0 / average_time if average_time > 0 else 0.0
    
    def _count_by_priority(self) -> Dict[int, int]:
        """Compte les requêtes par priorité"""
        priority_counts = {}
        for request in self._capture_queue:
            priority_counts[request.priority] = priority_counts.get(request.priority, 0) + 1
        return priority_counts
    
    def _notify_callbacks(self, result: CaptureResult) -> None:
        """Notifie tous les callbacks enregistrés"""
        for callback in self._capture_callbacks:
            try:
                callback(result)
            except Exception:
                # Ignorer les erreurs de callbacks
                pass
    
    def _start_periodic_capture(self) -> None:
        """Démarre le thread de capture périodique"""
        def periodic_worker():
            while not self._stop_periodic.wait(self.periodic_interval):
                if self.enable_periodic_capture:
                    self.trigger_manual_capture(priority=1)  # Basse priorité
        
        self._periodic_thread = threading.Thread(target=periodic_worker, daemon=True)
        self._periodic_thread.start()
    
    def _stop_periodic_capture(self) -> None:
        """Arrête le thread de capture périodique"""
        if self._periodic_thread:
            self._stop_periodic.set()
            self._periodic_thread.join(timeout=1.0)
            self._periodic_thread = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques complètes"""
        with self._lock:
            stats = self._stats.copy()
            stats.update(self.get_queue_status())
            stats.update({
                'total_captures': self._stats['successful_captures'] + self._stats['failed_captures'],
                'success_rate': (
                    self._stats['successful_captures'] / 
                    max(1, self._stats['successful_captures'] + self._stats['failed_captures'])
                )
            })
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'total_requests': 0,
                'successful_captures': 0,
                'failed_captures': 0,
                'average_capture_time': 0.0,
                'current_capture_rate': 0.0,
                'queue_size': 0
            }
            self._capture_times.clear()
    
    def clear_queue(self) -> None:
        """Vide la file de captures"""
        with self._lock:
            self._capture_queue.clear()
            self._pending_requests.clear()
    
    def shutdown(self) -> None:
        """Arrête proprement le déclencheur"""
        self._stop_periodic_capture()
        self.clear_queue()
