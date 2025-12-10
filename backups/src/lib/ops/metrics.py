"""
Metrics - Collection de KPI pour tous les layers S0-S6

Collecte et agrège les métriques de performance:
- KPI de scanning et reconnaissance
- Taux de réussite par layer
- Métriques de latence et throughput
- Intégration avec TraceRecorder S3
"""

import time
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from collections import defaultdict, deque

from ..s3_tensor.trace_recorder import TraceRecorder


class MetricType(Enum):
    """Types de métriques collectées"""
    COUNTER = "counter"           # Compteur cumulatif
    GAUGE = "gauge"              # Valeur instantanée
    HISTOGRAM = "histogram"      # Distribution de valeurs
    TIMER = "timer"              # Mesures de temps
    RATE = "rate"                # Taux par unité de temps


class LayerType(Enum):
    """Layers du système"""
    S0_NAVIGATION = "s0_navigation"
    S1_CAPTURE = "s1_capture"
    S2_RECOGNITION = "s2_recognition"
    S3_TENSOR = "s3_tensor"
    S4_SOLVER = "s4_solver"
    S5_ACTIONNEUR = "s5_actionneur"
    S6_PATHFINDER = "s6_pathfinder"


@dataclass
class MetricValue:
    """Valeur de métrique avec métadonnées"""
    name: str
    value: float
    metric_type: MetricType
    layer: LayerType
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            'name': self.name,
            'value': self.value,
            'type': self.metric_type.value,
            'layer': self.layer.value,
            'timestamp': self.timestamp,
            'tags': self.tags
        }


@dataclass
class LayerMetrics:
    """Métriques agrégées pour un layer"""
    layer: LayerType
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    average_latency: float = 0.0
    peak_latency: float = 0.0
    throughput: float = 0.0  # ops/seconde
    error_rate: float = 0.0
    last_update: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Taux de succès"""
        if self.total_operations == 0:
            return 0.0
        return self.successful_operations / self.total_operations
    
    def update(self, operation_time: float, success: bool) -> None:
        """Met à jour les métriques avec une nouvelle opération"""
        self.total_operations += 1
        self.last_update = time.time()
        
        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1
        
        # Mettre à jour la latence
        self._update_latency(operation_time)
        
        # Recalculer le taux d'erreur
        self.error_rate = self.failed_operations / self.total_operations
    
    def _update_latency(self, operation_time: float) -> None:
        """Met à jour les métriques de latence"""
        # Moyenne mobile simple
        if self.total_operations == 1:
            self.average_latency = operation_time
        else:
            alpha = 0.1  # Facteur de lissage
            self.average_latency = (
                alpha * operation_time + (1 - alpha) * self.average_latency
            )
        
        # Pic de latence
        self.peak_latency = max(self.peak_latency, operation_time)


class MetricsCollector:
    """
    Collecteur de métriques pour l'observabilité du système
    
    Fonctionnalités:
    - Collection des KPI de tous les layers
    - Agrégation en temps réel
    - Export vers TraceRecorder
    - Alertes sur les seuils critiques
    """
    
    def __init__(self, trace_recorder: Optional[TraceRecorder] = None,
                 enable_real_time_aggregation: bool = True,
                 aggregation_window: float = 60.0,
                 alert_thresholds: Optional[Dict[str, float]] = None):
        """
        Initialise le collecteur de métriques
        
        Args:
            trace_recorder: Enregistreur de traces S3 (optionnel)
            enable_real_time_aggregation: Activer l'agrégation en temps réel
            aggregation_window: Fenêtre d'agrégation en secondes
            alert_thresholds: Seuils d'alerte par métrique
        """
        # Dépendances
        self.trace_recorder = trace_recorder
        
        # Configuration
        self.enable_real_time_aggregation = enable_real_time_aggregation
        self.aggregation_window = aggregation_window
        self.alert_thresholds = alert_thresholds or {
            'error_rate': 0.1,      # 10% d'erreurs
            'latency': 1.0,         # 1 seconde
            'success_rate': 0.8     # 80% de succès
        }
        
        # État et stockage
        self._lock = threading.RLock()
        self._layer_metrics: Dict[LayerType, LayerMetrics] = {}
        self._metric_history: deque = deque(maxlen=10000)
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        
        # Initialiser les métriques par layer
        for layer in LayerType:
            self._layer_metrics[layer] = LayerMetrics(layer=layer)
        
        # Alertes
        self._alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._last_alert_check: float = 0.0
        
        # Thread d'agrégation
        self._aggregation_thread: Optional[threading.Thread] = None
        self._stop_aggregation = threading.Event()
        
        if self.enable_real_time_aggregation:
            self._start_aggregation_thread()
    
    def record_operation(self, layer: LayerType, operation_name: str,
                        operation_time: float, success: bool,
                        tags: Optional[Dict[str, str]] = None) -> None:
        """
        Enregistre une opération pour un layer
        
        Args:
            layer: Layer concerné
            operation_name: Nom de l'opération
            operation_time: Temps d'exécution
            success: Si l'opération a réussi
            tags: Tags additionnels
        """
        with self._lock:
            timestamp = time.time()
            
            # Mettre à jour les métriques du layer
            layer_metrics = self._layer_metrics[layer]
            layer_metrics.update(operation_time, success)
            
            # Enregistrer la métrique individuelle
            metric = MetricValue(
                name=f"{layer.value}_{operation_name}",
                value=operation_time,
                metric_type=MetricType.TIMER,
                layer=layer,
                timestamp=timestamp,
                tags=tags or {}
            )
            
            self._metric_history.append(metric)
            
            # Mettre à jour les compteurs
            counter_name = f"{layer.value}_operations_total"
            self._counters[counter_name] += 1
            
            if success:
                success_counter = f"{layer.value}_operations_successful"
                self._counters[success_counter] += 1
            else:
                error_counter = f"{layer.value}_operations_failed"
                self._counters[error_counter] += 1
            
            # Ajouter à l'histogramme de latence
            histogram_name = f"{layer.value}_latency_histogram"
            self._histograms[histogram_name].append(operation_time)
            
            # Limiter la taille des histogrammes
            if len(self._histograms[histogram_name]) > 1000:
                self._histograms[histogram_name] = self._histograms[histogram_name][-500:]
            
            # Exporter vers TraceRecorder
            if self.trace_recorder:
                self._export_to_trace_recorder(metric)
            
            # Vérifier les alertes
            self._check_alerts(layer, layer_metrics)
    
    def increment_counter(self, name: str, value: float = 1.0,
                         layer: Optional[LayerType] = None,
                         tags: Optional[Dict[str, str]] = None) -> None:
        """
        Incrémente un compteur
        
        Args:
            name: Nom du compteur
            value: Valeur à ajouter
            layer: Layer associé (optionnel)
            tags: Tags additionnels
        """
        with self._lock:
            full_name = f"{layer.value}_{name}" if layer else name
            self._counters[full_name] += value
            
            metric = MetricValue(
                name=full_name,
                value=self._counters[full_name],
                metric_type=MetricType.COUNTER,
                layer=layer or LayerType.S3_TENSOR,  # Layer par défaut
                timestamp=time.time(),
                tags=tags or {}
            )
            
            self._metric_history.append(metric)
    
    def set_gauge(self, name: str, value: float,
                 layer: Optional[LayerType] = None,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
        Définit la valeur d'une jauge
        
        Args:
            name: Nom de la jauge
            value: Valeur à définir
            layer: Layer associé (optionnel)
            tags: Tags additionnels
        """
        with self._lock:
            full_name = f"{layer.value}_{name}" if layer else name
            self._gauges[full_name] = value
            
            metric = MetricValue(
                name=full_name,
                value=value,
                metric_type=MetricType.GAUGE,
                layer=layer or LayerType.S3_TENSOR,
                timestamp=time.time(),
                tags=tags or {}
            )
            
            self._metric_history.append(metric)
    
    def record_histogram(self, name: str, value: float,
                        layer: Optional[LayerType] = None,
                        tags: Optional[Dict[str, str]] = None) -> None:
        """
        Enregistre une valeur dans un histogramme
        
        Args:
            name: Nom de l'histogramme
            value: Valeur à enregistrer
            layer: Layer associé (optionnel)
            tags: Tags additionnels
        """
        with self._lock:
            full_name = f"{layer.value}_{name}" if layer else name
            self._histograms[full_name].append(value)
            
            # Limiter la taille
            if len(self._histograms[full_name]) > 1000:
                self._histograms[full_name] = self._histograms[full_name][-500:]
            
            metric = MetricValue(
                name=full_name,
                value=value,
                metric_type=MetricType.HISTOGRAM,
                layer=layer or LayerType.S3_TENSOR,
                timestamp=time.time(),
                tags=tags or {}
            )
            
            self._metric_history.append(metric)
    
    def get_layer_metrics(self, layer: LayerType) -> LayerMetrics:
        """
        Retourne les métriques d'un layer
        
        Args:
            layer: Layer concerné
            
        Returns:
            Métriques du layer
        """
        with self._lock:
            return self._layer_metrics[layer]
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques globales du système"""
        with self._lock:
            total_ops = sum(m.total_operations for m in self._layer_metrics.values())
            total_successful = sum(m.successful_operations for m in self._layer_metrics.values())
            total_failed = sum(m.failed_operations for m in self._layer_metrics.values())
            
            # Calculer le throughput global
            current_time = time.time()
            recent_ops = [
                m for m in self._metric_history
                if current_time - m.timestamp < self.aggregation_window
            ]
            
            throughput = len(recent_ops) / self.aggregation_window if recent_ops else 0.0
            
            return {
                'total_operations': total_ops,
                'successful_operations': total_successful,
                'failed_operations': total_failed,
                'overall_success_rate': total_successful / max(1, total_ops),
                'overall_error_rate': total_failed / max(1, total_ops),
                'system_throughput': throughput,
                'metrics_collected': len(self._metric_history),
                'layers_count': len(self._layer_metrics),
                'last_update': current_time
            }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des performances par layer"""
        with self._lock:
            summary = {}
            
            for layer, metrics in self._layer_metrics.items():
                summary[layer.value] = {
                    'total_operations': metrics.total_operations,
                    'success_rate': metrics.success_rate,
                    'error_rate': metrics.error_rate,
                    'average_latency': metrics.average_latency,
                    'peak_latency': metrics.peak_latency,
                    'throughput': metrics.throughput,
                    'last_update': metrics.last_update
                }
            
            return summary
    
    def register_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        Enregistre un callback d'alerte
        
        Args:
            callback: Fonction appelée en cas d'alerte
        """
        with self._lock:
            self._alert_callbacks.append(callback)
    
    def _export_to_trace_recorder(self, metric: MetricValue) -> None:
        """Exporte une métrique vers TraceRecorder"""
        if self.trace_recorder:
            try:
                trace_data = {
                    'metric': metric.to_dict(),
                    'timestamp': metric.timestamp,
                    'source': 'metrics_collector'
                }
                
                self.trace_recorder.record_trace('metric', trace_data)
            except Exception:
                # Ignorer les erreurs d'export
                pass
    
    def _check_alerts(self, layer: LayerType, metrics: LayerMetrics) -> None:
        """Vérifie les conditions d'alerte"""
        current_time = time.time()
        
        # Vérifier les alertes seulement toutes les 10 secondes
        if current_time - self._last_alert_check < 10.0:
            return
        
        self._last_alert_check = current_time
        
        alerts = []
        
        # Vérifier le taux d'erreur
        if metrics.error_rate > self.alert_thresholds['error_rate']:
            alerts.append({
                'type': 'high_error_rate',
                'layer': layer.value,
                'value': metrics.error_rate,
                'threshold': self.alert_thresholds['error_rate']
            })
        
        # Vérifier la latence
        if metrics.average_latency > self.alert_thresholds['latency']:
            alerts.append({
                'type': 'high_latency',
                'layer': layer.value,
                'value': metrics.average_latency,
                'threshold': self.alert_thresholds['latency']
            })
        
        # Vérifier le taux de succès
        if metrics.success_rate < self.alert_thresholds['success_rate']:
            alerts.append({
                'type': 'low_success_rate',
                'layer': layer.value,
                'value': metrics.success_rate,
                'threshold': self.alert_thresholds['success_rate']
            })
        
        # Déclencher les alertes
        for alert in alerts:
            for callback in self._alert_callbacks:
                try:
                    callback('metric_alert', alert)
                except Exception:
                    # Ignorer les erreurs de callbacks
                    pass
    
    def _start_aggregation_thread(self) -> None:
        """Démarre le thread d'agrégation en temps réel"""
        def aggregation_worker():
            while not self._stop_aggregation.wait(1.0):
                self._perform_aggregation()
        
        self._aggregation_thread = threading.Thread(target=aggregation_worker, daemon=True)
        self._aggregation_thread.start()
    
    def _perform_aggregation(self) -> None:
        """Effectue l'agrégation en temps réel"""
        with self._lock:
            current_time = time.time()
            
            # Calculer le throughput pour chaque layer
            for layer, metrics in self._layer_metrics.items():
                recent_metrics = [
                    m for m in self._metric_history
                    if (m.layer == layer and 
                        current_time - m.timestamp < self.aggregation_window)
                ]
                
                metrics.throughput = len(recent_metrics) / self.aggregation_window
    
    def _stop_aggregation_thread(self) -> None:
        """Arrête le thread d'agrégation"""
        if self._aggregation_thread:
            self._stop_aggregation.set()
            self._aggregation_thread.join(timeout=1.0)
            self._aggregation_thread = None
    
    def export_metrics(self, format_type: str = 'dict') -> Any:
        """
        Exporte toutes les métriques
        
        Args:
            format_type: Format d'export ('dict', 'json', 'csv')
            
        Returns:
            Métriques exportées
        """
        with self._lock:
            if format_type == 'dict':
                return {
                    'system_metrics': self.get_system_metrics(),
                    'layer_metrics': self.get_performance_summary(),
                    'counters': dict(self._counters),
                    'gauges': dict(self._gauges),
                    'histograms': {k: {
                        'count': len(v),
                        'sum': sum(v),
                        'avg': np.mean(v) if v else 0.0,
                        'min': min(v) if v else 0.0,
                        'max': max(v) if v else 0.0
                    } for k, v in self._histograms.items()},
                    'export_timestamp': time.time()
                }
            
            # Autres formats à implémenter
            return self.get_system_metrics()
    
    def reset_metrics(self, layer: Optional[LayerType] = None) -> None:
        """
        Réinitialise les métriques
        
        Args:
            layer: Layer spécifique à réinitialiser (None = tous)
        """
        with self._lock:
            if layer:
                self._layer_metrics[layer] = LayerMetrics(layer=layer)
            else:
                for l in LayerType:
                    self._layer_metrics[l] = LayerMetrics(layer=l)
            
            # Vider l'historique
            self._metric_history.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
    
    def shutdown(self) -> None:
        """Arrête proprement le collecteur"""
        self._stop_aggregation_thread()
