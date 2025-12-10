"""
ActionLogger - Journalisation et traçabilité des actions (S5.3)

Gère le log append-only des actions et met à jour TensorGrid:
- Trace log détaillé de toutes les actions exécutées
- Mise à jour de TensorGrid après exécution
- Publication d'état des zones vers S6 Pathfinder
- Interface de persistance et analyse
"""

import numpy as np
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
import json
from pathlib import Path
import hashlib

from .s52_action_executor import ExecutionReport, ExecutionResult
from .s51_action_queue import QueuedAction
from ..s4_solver.hybrid_solver import SolverAction
from ..s3_tensor.tensor_grid import TensorGrid, GridBounds, CellSymbol, DirtyRegion
from ..s3_tensor.hint_cache import HintCache, HintType


class ZoneStatus(Enum):
    """Statuts des zones pour feedback S6"""
    RESOLVED = "resolved"  # Zone complètement résolue
    BLOCKED = "blocked"    # Zone bloquée (plus d'actions possibles)
    CRITICAL = "critical"  # Zone nécessitant une attention immédiate
    ACTIVE = "active"      # Zone encore active avec des actions possibles


@dataclass
class ActionTrace:
    """Trace individuelle d'une action exécutée"""
    trace_id: str
    action: SolverAction
    execution_report: ExecutionReport
    timestamp: float
    
    # État avant/après
    pre_execution_state: Dict[str, Any] = field(default_factory=dict)
    post_execution_state: Dict[str, Any] = field(default_factory=dict)
    
    # Métadonnées
    solver_confidence: float = 0.0
    zone_bounds: Optional[GridBounds] = None
    zone_status_before: ZoneStatus = ZoneStatus.ACTIVE
    zone_status_after: ZoneStatus = ZoneStatus.ACTIVE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la trace en dictionnaire pour sérialisation"""
        return {
            'trace_id': self.trace_id,
            'action': {
                'type': self.action.action_type,
                'coordinates': self.action.coordinates,
                'confidence': self.action.confidence,
                'reasoning': self.action.reasoning,
                'solver_engine': self.action.solver_engine
            },
            'execution': {
                'result': self.execution_report.result.value,
                'execution_time': self.execution_report.execution_time,
                'error_message': self.execution_report.error_message
            },
            'timestamp': self.timestamp,
            'pre_state': self.pre_execution_state,
            'post_state': self.post_execution_state,
            'zone_status_before': self.zone_status_before.value,
            'zone_status_after': self.zone_status_after.value
        }


@dataclass
class ZoneUpdate:
    """Mise à jour d'une zone pour S6"""
    zone_bounds: GridBounds
    status: ZoneStatus
    timestamp: float
    action_count: int
    success_rate: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class ActionLogger:
    """
    Journaliseur d'actions avec mise à jour TensorGrid
    
    Fonctionnalités:
    - Log append-only de toutes les actions
    - Mise à jour de TensorGrid après exécution
    - Analyse de l'état des zones pour S6
    - Persistance et relecture des traces
    """
    
    def __init__(self, tensor_grid: TensorGrid, hint_cache: HintCache,
                 log_file_path: Optional[str] = None,
                 max_memory_traces: int = 1000,
                 persist_interval: int = 100,
                 enable_zone_analysis: bool = True):
        """
        Initialise le journaliseur d'actions
        
        Args:
            tensor_grid: Grille tensorielle à mettre à jour
            hint_cache: Cache pour publier les états de zones
            log_file_path: Chemin du fichier de log (None = mémoire seulement)
            max_memory_traces: Nombre maximum de traces en mémoire
            persist_interval: Intervalle de persistance des traces
            enable_zone_analysis: Activer l'analyse des zones
        """
        self._lock = threading.RLock()
        
        # Dépendances
        self.tensor_grid = tensor_grid
        self.hint_cache = hint_cache
        
        # Configuration
        self.log_file_path = log_file_path
        self.max_memory_traces = max_memory_traces
        self.persist_interval = persist_interval
        self.enable_zone_analysis = enable_zone_analysis
        
        # État interne
        self._action_traces: List[ActionTrace] = []
        self._zone_updates: List[ZoneUpdate] = []
        self._zone_status_cache: Dict[str, ZoneStatus] = {}
        
        # Compteurs
        self._trace_counter: int = 0
        self._persist_counter: int = 0
        
        # Statistiques
        self._stats = {
            'total_actions_logged': 0,
            'successful_actions': 0,
            'failed_actions': 0,
            'zones_resolved': 0,
            'zones_blocked': 0,
            'average_action_confidence': 0.0,
            'tensor_grid_updates': 0
        }
        
        # Créer le répertoire de log si nécessaire
        if self.log_file_path:
            Path(self.log_file_path).parent.mkdir(parents=True, exist_ok=True)
    
    def log_action_execution(self, queued_action: QueuedAction, 
                            execution_report: ExecutionReport) -> str:
        """
        Enregistre l'exécution d'une action
        
        Args:
            queued_action: Action exécutée
            execution_report: Rapport d'exécution
            
        Returns:
            ID de la trace créée
        """
        with self._lock:
            # Capturer l'état avant exécution
            pre_state = self._capture_cell_state(queued_action.action.coordinates)
            
            # Créer la trace
            trace_id = f"trace_{self._trace_counter}"
            self._trace_counter += 1
            
            action_trace = ActionTrace(
                trace_id=trace_id,
                action=queued_action.action,
                execution_report=execution_report,
                timestamp=time.time(),
                pre_execution_state=pre_state,
                solver_confidence=queued_action.action.confidence
            )
            
            # Mettre à jour TensorGrid si succès
            if execution_report.result == ExecutionResult.SUCCESS:
                self._update_tensor_grid_after_action(queued_action.action)
                action_trace.post_execution_state = self._capture_cell_state(
                    queued_action.action.coordinates
                )
            
            # Analyser l'impact sur les zones
            if self.enable_zone_analysis:
                zone_update = self._analyze_zone_impact(action_trace)
                if zone_update:
                    self._zone_updates.append(zone_update)
                    self._publish_zone_update(zone_update)
            
            # Ajouter à l'historique
            self._action_traces.append(action_trace)
            
            # Limiter la taille en mémoire
            if len(self._action_traces) > self.max_memory_traces:
                self._action_traces = self._action_traces[-self.max_memory_traces // 2:]
            
            # Persister si nécessaire
            self._persist_counter += 1
            if self._persist_counter >= self.persist_interval:
                self._persist_traces()
                self._persist_counter = 0
            
            # Mettre à jour les statistiques
            self._update_logging_stats(action_trace)
            
            return trace_id
    
    def _capture_cell_state(self, coordinates: Tuple[int, int]) -> Dict[str, Any]:
        """Capture l'état d'une cellule dans TensorGrid"""
        x, y = coordinates
        solver_view = self.tensor_grid.get_solver_view()
        offset = solver_view['global_offset']
        
        local_x = x - offset[0]
        local_y = y - offset[1]
        
        if (0 <= local_x < solver_view['symbols'].shape[1] and 
            0 <= local_y < solver_view['symbols'].shape[0]):
            
            return {
                'symbol': int(solver_view['symbols'][local_y, local_x]),
                'confidence': float(solver_view['confidence'][local_y, local_x]),
                'is_frontier': bool(solver_view['frontier_mask'][local_y, local_x])
            }
        
        return {'symbol': -1, 'confidence': 0.0, 'is_frontier': False}
    
    def _update_tensor_grid_after_action(self, action: SolverAction) -> None:
        """Met à jour TensorGrid après une action réussie"""
        x, y = action.coordinates
        
        # Créer une région de mise à jour pour la cellule
        bounds = GridBounds(x, y, x, y)
        
        if action.action_type == 'flag':
            # Marquer comme flaggé (utiliser un symbole spécial)
            symbols = np.array([[CellSymbol.FLAGGED]], dtype=np.int8)
            confidence = np.array([[1.0]], dtype=np.float32)
            
        elif action.action_type in ['reveal', 'guess']:
            # Pour reveal/guess, on ne connaît pas encore le résultat
            # Laisser le système de reconnaissance mettre à jour
            return
            
        else:
            return
        
        # Mettre à jour TensorGrid
        self.tensor_grid.update_region(
            bounds=bounds,
            symbols=symbols,
            confidence=confidence,
            frontier_mask=np.array([[False]], dtype=bool)
        )
        
        self._stats['tensor_grid_updates'] += 1
    
    def _analyze_zone_impact(self, trace: ActionTrace) -> Optional[ZoneUpdate]:
        """Analyse l'impact de l'action sur les zones environnantes"""
        x, y = trace.action.coordinates
        
        # Définir une zone autour de l'action
        zone_size = 15
        zone_bounds = GridBounds(
            x_min=max(0, x - zone_size),
            y_min=max(0, y - zone_size),
            x_max=x + zone_size,
            y_max=y + zone_size
        )
        
        # Analyser l'état de la zone
        solver_view = self.tensor_grid.get_solver_view()
        zone_status = self._evaluate_zone_status(zone_bounds, solver_view)
        
        # Créer la mise à jour
        zone_update = ZoneUpdate(
            zone_bounds=zone_bounds,
            status=zone_status,
            timestamp=trace.timestamp,
            action_count=1,  # Pour l'instant, une action à la fois
            success_rate=1.0 if trace.execution_report.result == ExecutionResult.SUCCESS else 0.0,
            metadata={
                'action_type': trace.action.action_type,
                'solver_engine': trace.action.solver_engine,
                'trace_id': trace.trace_id
            }
        )
        
        return zone_update
    
    def _evaluate_zone_status(self, bounds: GridBounds, solver_view: Dict[str, Any]) -> ZoneStatus:
        """Évalue le statut d'une zone"""
        offset = solver_view['global_offset']
        
        # Extraire la région
        local_x_min = max(0, bounds.x_min - offset[0])
        local_y_min = max(0, bounds.y_min - offset[1])
        local_x_max = min(solver_view['symbols'].shape[1] - 1, bounds.x_max - offset[0])
        local_y_max = min(solver_view['symbols'].shape[0] - 1, bounds.y_max - offset[1])
        
        if local_x_min > local_x_max or local_y_min > local_y_max:
            return ZoneStatus.ACTIVE
        
        region_symbols = solver_view['symbols'][local_y_min:local_y_max+1, 
                                               local_x_min:local_x_max+1]
        region_frontier = solver_view['frontier_mask'][local_y_min:local_y_max+1,
                                                     local_x_min:local_x_max+1]
        
        total_cells = region_symbols.size
        unknown_cells = np.sum(region_symbols == CellSymbol.UNKNOWN)
        frontier_cells = np.sum(region_frontier)
        
        # Évaluer le statut
        if unknown_cells == 0:
            return ZoneStatus.RESOLVED
        elif frontier_cells == 0 and unknown_cells > 0:
            return ZoneStatus.BLOCKED
        elif frontier_cells > total_cells * 0.5:
            return ZoneStatus.CRITICAL
        else:
            return ZoneStatus.ACTIVE
    
    def _publish_zone_update(self, zone_update: ZoneUpdate) -> None:
        """Publie la mise à jour de zone vers HintCache pour S6"""
        # Créer un hint pour S6 Pathfinder
        hint_data = {
            'zone_bounds': zone_update.zone_bounds,
            'status': zone_update.status.value,
            'action_count': zone_update.action_count,
            'success_rate': zone_update.success_rate,
            'timestamp': zone_update.timestamp
        }
        
        # Publier via HintCache
        self.hint_cache.publish_hint(
            hint_type=HintType.SOLVER_FEEDBACK,
            solver_bounds=zone_update.zone_bounds,
            success_rate=zone_update.success_rate,
            metadata=hint_data
        )
    
    def _update_logging_stats(self, trace: ActionTrace) -> None:
        """Met à jour les statistiques de logging"""
        self._stats['total_actions_logged'] += 1
        
        if trace.execution_report.result == ExecutionResult.SUCCESS:
            self._stats['successful_actions'] += 1
        else:
            self._stats['failed_actions'] += 1
        
        # Mettre à jour la confiance moyenne
        total_logged = self._stats['total_actions_logged']
        current_avg = self._stats['average_action_confidence']
        self._stats['average_action_confidence'] = (
            (current_avg * (total_logged - 1) + trace.solver_confidence) / total_logged
        )
    
    def _persist_traces(self) -> None:
        """Persiste les traces en mémoire vers le fichier"""
        if not self.log_file_path:
            return
        
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                for trace in self._action_traces[-self.persist_interval:]:
                    json.dump(trace.to_dict(), f, ensure_ascii=False)
                    f.write('\n')
        except Exception as e:
            print(f"Failed to persist traces: {e}")
    
    def get_action_history(self, limit: int = 100, 
                          action_type: Optional[str] = None) -> List[ActionTrace]:
        """
        Retourne l'historique des actions
        
        Args:
            limit: Nombre maximum de traces
            action_type: Filtrer par type d'action
            
        Returns:
            Liste des traces correspondantes
        """
        with self._lock:
            traces = self._action_traces[-limit:] if limit > 0 else self._action_traces
            
            if action_type:
                traces = [t for t in traces if t.action.action_type == action_type]
            
            return traces
    
    def get_zone_updates(self, since: Optional[float] = None) -> List[ZoneUpdate]:
        """
        Retourne les mises à jour de zones
        
        Args:
            since: Timestamp minimum (None = toutes)
            
        Returns:
            Liste des mises à jour de zones
        """
        with self._lock:
            updates = self._zone_updates
            
            if since:
                updates = [u for u in updates if u.timestamp >= since]
            
            return updates
    
    def get_recent_zone_status(self, bounds: GridBounds) -> Optional[ZoneStatus]:
        """Retourne le statut le plus récent pour une zone"""
        with self._lock:
            # Chercher la mise à jour la plus récente pour cette zone
            relevant_updates = [
                u for u in self._zone_updates
                if self._bounds_overlap(u.zone_bounds, bounds)
            ]
            
            if not relevant_updates:
                return None
            
            # Retourner le statut de la mise à jour la plus récente
            latest_update = max(relevant_updates, key=lambda u: u.timestamp)
            return latest_update.status
    
    def _bounds_overlap(self, bounds1: GridBounds, bounds2: GridBounds) -> bool:
        """Vérifie si deux bornes se chevauchent"""
        return not (bounds1.x_max < bounds2.x_min or bounds1.x_min > bounds2.x_max or
                   bounds1.y_max < bounds2.y_min or bounds1.y_min > bounds2.y_max)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de performance"""
        with self._lock:
            if not self._action_traces:
                return {}
            
            # Calculer les métriques
            recent_traces = self._action_traces[-100:]  # 100 dernières actions
            
            success_rate = (
                sum(1 for t in recent_traces if t.execution_report.result == ExecutionResult.SUCCESS) /
                len(recent_traces)
            )
            
            avg_execution_time = np.mean([t.execution_report.execution_time for t in recent_traces])
            
            # Taux par type d'action
            type_stats = {}
            for trace in recent_traces:
                action_type = trace.action.action_type
                if action_type not in type_stats:
                    type_stats[action_type] = {'total': 0, 'success': 0}
                type_stats[action_type]['total'] += 1
                if trace.execution_report.result == ExecutionResult.SUCCESS:
                    type_stats[action_type]['success'] += 1
            
            for action_type in type_stats:
                total = type_stats[action_type]['total']
                success = type_stats[action_type]['success']
                type_stats[action_type]['success_rate'] = success / total
            
            return {
                'recent_success_rate': success_rate,
                'average_execution_time': avg_execution_time,
                'action_type_stats': type_stats,
                'total_zones_analyzed': len(set(u.zone_bounds for u in self._zone_updates))
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du journaliseur"""
        with self._lock:
            stats = self._stats.copy()
            stats.update({
                'memory_traces_count': len(self._action_traces),
                'zone_updates_count': len(self._zone_updates),
                'persist_counter': self._persist_counter
            })
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'total_actions_logged': 0,
                'successful_actions': 0,
                'failed_actions': 0,
                'zones_resolved': 0,
                'zones_blocked': 0,
                'average_action_confidence': 0.0,
                'tensor_grid_updates': 0
            }
    
    def clear_history(self) -> None:
        """Efface tout l'historique"""
        with self._lock:
            self._action_traces.clear()
            self._zone_updates.clear()
            self._zone_status_cache.clear()
    
    def export_traces(self, file_path: str, format: str = 'json') -> bool:
        """
        Exporte les traces vers un fichier
        
        Args:
            file_path: Chemin du fichier d'export
            format: Format d'export ('json' ou 'csv')
            
        Returns:
            True si succès, False si échec
        """
        try:
            if format == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([t.to_dict() for t in self._action_traces], f, 
                             indent=2, ensure_ascii=False)
            elif format == 'csv':
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    if not self._action_traces:
                        return True
                    
                    # En-têtes CSV
                    fieldnames = ['trace_id', 'action_type', 'coordinates', 'confidence', 
                                 'result', 'execution_time', 'timestamp']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    # Données
                    for trace in self._action_traces:
                        writer.writerow({
                            'trace_id': trace.trace_id,
                            'action_type': trace.action.action_type,
                            'coordinates': f"{trace.action.coordinates[0]},{trace.action.coordinates[1]}",
                            'confidence': trace.action.confidence,
                            'result': trace.execution_report.result.value,
                            'execution_time': trace.execution_report.execution_time,
                            'timestamp': trace.timestamp
                        })
            
            return True
            
        except Exception as e:
            print(f"Export failed: {e}")
            return False
