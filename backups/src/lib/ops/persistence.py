"""
Persistence - Système de persistance et dashboards (Ops)

Gère la persistance des données et les dashboards:
- Intégration avec TraceRecorder S3
- Sauvegarde automatique des états
- Dashboards de monitoring
- Reprise après crash
"""

import json
import time
import threading
import pickle
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import sqlite3
import numpy as np

from ..s3_tensor.trace_recorder import TraceRecorder
from ..s3_tensor.tensor_grid import TensorGrid, GridBounds


class PersistenceFormat(Enum):
    """Formats de persistance"""
    JSON = "json"
    PICKLE = "pickle"
    SQLITE = "sqlite"
    PARQUET = "parquet"


class BackupFrequency(Enum):
    """Fréquences de sauvegarde"""
    REAL_TIME = "real_time"
    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"


@dataclass
class BackupConfig:
    """Configuration de sauvegarde"""
    frequency: BackupFrequency
    format: PersistenceFormat
    compression: bool = True
    max_backups: int = 10
    backup_path: str = "backups"
    
    def should_backup(self, last_backup: float) -> bool:
        """Vérifie si une sauvegarde est nécessaire"""
        current_time = time.time()
        
        if self.frequency == BackupFrequency.REAL_TIME:
            return True
        elif self.frequency == BackupFrequency.MINUTELY:
            return current_time - last_backup >= 60
        elif self.frequency == BackupFrequency.HOURLY:
            return current_time - last_backup >= 3600
        elif self.frequency == BackupFrequency.DAILY:
            return current_time - last_backup >= 86400
        
        return False


@dataclass
class DashboardData:
    """Données pour dashboard"""
    timestamp: float
    system_metrics: Dict[str, Any]
    layer_metrics: Dict[str, Any]
    tensor_grid_stats: Dict[str, Any]
    performance_trends: Dict[str, List[float]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'timestamp': self.timestamp,
            'system_metrics': self.system_metrics,
            'layer_metrics': self.layer_metrics,
            'tensor_grid_stats': self.tensor_grid_stats,
            'performance_trends': self.performance_trends
        }


class PersistenceManager:
    """
    Gestionnaire de persistance pour l'observabilité
    
    Fonctionnalités:
    - Sauvegarde automatique des états
    - Intégration avec TraceRecorder S3
    - Dashboards de monitoring
    - Reprise après crash
    """
    
    def __init__(self, trace_recorder: TraceRecorder,
                 backup_config: Optional[BackupConfig] = None,
                 enable_dashboard: bool = True,
                 dashboard_path: str = "dashboards"):
        """
        Initialise le gestionnaire de persistance
        
        Args:
            trace_recorder: Enregistreur de traces S3
            backup_config: Configuration de sauvegarde
            enable_dashboard: Activer les dashboards
            dashboard_path: Chemin des dashboards
        """
        # Dépendances
        self.trace_recorder = trace_recorder
        
        # Configuration
        self.backup_config = backup_config or BackupConfig(
            frequency=BackupFrequency.HOURLY,
            format=PersistenceFormat.JSON,
            backup_path="backups"
        )
        self.enable_dashboard = enable_dashboard
        self.dashboard_path = dashboard_path
        
        # État et stockage
        self._lock = threading.RLock()
        self._last_backup_time: float = 0.0
        self._backup_thread: Optional[threading.Thread] = None
        self._stop_backup = threading.Event()
        
        # Données de dashboard
        self._dashboard_history: List[DashboardData] = []
        self._performance_trends: Dict[str, List[float]] = {}
        
        # Base de données SQLite pour les métriques
        self._db_connection: Optional[sqlite3.Connection] = None
        self._db_path = f"{dashboard_path}/metrics.db"
        
        # Statistiques
        self._stats = {
            'backups_performed': 0,
            'last_backup_size': 0,
            'dashboard_snapshots': 0,
            'db_records': 0,
            'recovery_attempts': 0
        }
        
        # Initialiser
        self._initialize()
    
    def backup_tensor_grid(self, tensor_grid: TensorGrid,
                           backup_name: Optional[str] = None) -> bool:
        """
        Sauvegarde l'état de TensorGrid
        
        Args:
            tensor_grid: Grille tensorielle à sauvegarder
            backup_name: Nom de la sauvegarde (optionnel)
            
        Returns:
            True si la sauvegarde a réussi
        """
        try:
            if not self.backup_config.should_backup(self._last_backup_time):
                return True
            
            # Générer le nom de fichier
            timestamp = int(time.time())
            backup_name = backup_name or f"tensor_grid_{timestamp}"
            
            # Extraire les données de TensorGrid
            grid_data = {
                'symbols': tensor_grid._symbols.tolist(),
                'confidence': tensor_grid._confidence.tolist(),
                'age': tensor_grid._age.tolist(),
                'frontier_mask': tensor_grid._frontier_mask.tolist(),
                'global_offset': tensor_grid._global_offset,
                'bounds': tensor_grid.get_bounds().__dict__,
                'timestamp': timestamp,
                'stats': tensor_grid.get_stats()
            }
            
            # Sauvegarder selon le format
            if self.backup_config.format == PersistenceFormat.JSON:
                success = self._save_json(backup_name, grid_data)
            elif self.backup_config.format == PersistenceFormat.PICKLE:
                success = self._save_pickle(backup_name, grid_data)
            elif self.backup_config.format == PersistenceFormat.SQLITE:
                success = self._save_sqlite(backup_name, grid_data)
            else:
                success = False
            
            if success:
                self._last_backup_time = time.time()
                self._stats['backups_performed'] += 1
                
                # Enregistrer dans TraceRecorder
                self.trace_recorder.record_trace('backup', {
                    'type': 'tensor_grid',
                    'name': backup_name,
                    'format': self.backup_config.format.value,
                    'timestamp': timestamp
                })
            
            return success
            
        except Exception:
            return False
    
    def restore_tensor_grid(self, backup_name: str) -> Optional[TensorGrid]:
        """
        Restaure TensorGrid depuis une sauvegarde
        
        Args:
            backup_name: Nom de la sauvegarde à restaurer
            
        Returns:
            TensorGrid restauré ou None si échec
        """
        try:
            self._stats['recovery_attempts'] += 1
            
            # Charger selon le format
            if self.backup_config.format == PersistenceFormat.JSON:
                grid_data = self._load_json(backup_name)
            elif self.backup_config.format == PersistenceFormat.PICKLE:
                grid_data = self._load_pickle(backup_name)
            elif self.backup_config.format == PersistenceFormat.SQLITE:
                grid_data = self._load_sqlite(backup_name)
            else:
                return None
            
            if not grid_data:
                return None
            
            # Recréer TensorGrid
            bounds_data = grid_data['bounds']
            bounds = GridBounds(
                x_min=bounds_data['x_min'],
                y_min=bounds_data['y_min'],
                x_max=bounds_data['x_max'],
                y_max=bounds_data['y_max']
            )
            
            tensor_grid = TensorGrid(bounds)
            
            # Restaurer les arrays
            tensor_grid._symbols = np.array(grid_data['symbols'], dtype=np.int8)
            tensor_grid._confidence = np.array(grid_data['confidence'], dtype=np.float32)
            tensor_grid._age = np.array(grid_data['age'], dtype=np.uint64)
            tensor_grid._frontier_mask = np.array(grid_data['frontier_mask'], dtype=bool)
            tensor_grid._global_offset = tuple(grid_data['global_offset'])
            
            # Enregistrer la restauration
            self.trace_recorder.record_trace('restore', {
                'type': 'tensor_grid',
                'name': backup_name,
                'timestamp': time.time()
            })
            
            return tensor_grid
            
        except Exception:
            return None
    
    def create_dashboard_snapshot(self, system_metrics: Dict[str, Any],
                                 layer_metrics: Dict[str, Any],
                                 tensor_grid: TensorGrid) -> DashboardData:
        """
        Crée un snapshot pour le dashboard
        
        Args:
            system_metrics: Métriques système
            layer_metrics: Métriques des layers
            tensor_grid: Grille tensorielle
            
        Returns:
            Données du dashboard
        """
        timestamp = time.time()
        
        # Mettre à jour les tendances de performance
        self._update_performance_trends(system_metrics, layer_metrics)
        
        # Créer les données du dashboard
        dashboard_data = DashboardData(
            timestamp=timestamp,
            system_metrics=system_metrics,
            layer_metrics=layer_metrics,
            tensor_grid_stats=tensor_grid.get_stats(),
            performance_trends=self._performance_trends.copy()
        )
        
        # Ajouter à l'historique
        with self._lock:
            self._dashboard_history.append(dashboard_data)
            
            # Limiter l'historique
            if len(self._dashboard_history) > 1000:
                self._dashboard_history = self._dashboard_history[-500:]
            
            self._stats['dashboard_snapshots'] += 1
        
        # Sauvegarder dans la base de données
        if self._db_connection:
            self._save_to_database(dashboard_data)
        
        return dashboard_data
    
    def get_dashboard_data(self, time_range: Optional[float] = None) -> List[DashboardData]:
        """
        Retourne les données du dashboard
        
        Args:
            time_range: Plage temporelle en secondes (None = toutes)
            
        Returns:
            Données du dashboard
        """
        with self._lock:
            if time_range is None:
                return self._dashboard_history.copy()
            
            current_time = time.time()
            cutoff_time = current_time - time_range
            
            return [
                data for data in self._dashboard_history
                if data.timestamp >= cutoff_time
            ]
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Génère un rapport de performance"""
        with self._lock:
            if not self._dashboard_history:
                return {'error': 'No data available'}
            
            # Données récentes (dernière heure)
            recent_data = self.get_dashboard_data(3600)
            
            if not recent_data:
                return {'error': 'No recent data'}
            
            # Calculer les moyennes
            avg_success_rate = np.mean([
                d.system_metrics.get('overall_success_rate', 0) 
                for d in recent_data
            ])
            
            avg_latency = np.mean([
                d.system_metrics.get('average_latency', 0)
                for d in recent_data
            ])
            
            avg_throughput = np.mean([
                d.system_metrics.get('system_throughput', 0)
                for d in recent_data
            ])
            
            # Tendances
            success_trend = self._calculate_trend('overall_success_rate')
            latency_trend = self._calculate_trend('average_latency')
            
            return {
                'period': 'Last hour',
                'snapshots_count': len(recent_data),
                'averages': {
                    'success_rate': avg_success_rate,
                    'latency': avg_latency,
                    'throughput': avg_throughput
                },
                'trends': {
                    'success_rate': success_trend,
                    'latency': latency_trend
                },
                'tensor_grid': recent_data[-1].tensor_grid_stats if recent_data else {},
                'last_update': recent_data[-1].timestamp if recent_data else 0
            }
    
    def _initialize(self) -> None:
        """Initialise le gestionnaire"""
        # Créer les répertoires
        Path(self.backup_config.backup_path).mkdir(parents=True, exist_ok=True)
        Path(self.dashboard_path).mkdir(parents=True, exist_ok=True)
        
        # Initialiser la base de données
        if self.enable_dashboard:
            self._initialize_database()
        
        # Démarrer le thread de sauvegarde
        self._start_backup_thread()
    
    def _initialize_database(self) -> None:
        """Initialise la base de données SQLite"""
        try:
            self._db_connection = sqlite3.connect(self._db_path, check_same_thread=False)
            
            # Créer les tables
            cursor = self._db_connection.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dashboard_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    system_metrics TEXT NOT NULL,
                    layer_metrics TEXT NOT NULL,
                    tensor_grid_stats TEXT NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_trends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp REAL NOT NULL
                )
            ''')
            
            self._db_connection.commit()
            
        except Exception as e:
            print(f"Failed to initialize database: {e}")
            self._db_connection = None
    
    def _start_backup_thread(self) -> None:
        """Démarre le thread de sauvegarde automatique"""
        if self.backup_config.frequency == BackupFrequency.REAL_TIME:
            return  # Pas de thread pour le temps réel
        
        def backup_worker():
            while not self._stop_backup.wait(60):  # Vérifier chaque minute
                if self.backup_config.should_backup(self._last_backup_time):
                    # Déclencher une sauvegarde via callback
                    pass
        
        self._backup_thread = threading.Thread(target=backup_worker, daemon=True)
        self._backup_thread.start()
    
    def _save_json(self, name: str, data: Dict[str, Any]) -> bool:
        """Sauvegarde en format JSON"""
        try:
            file_path = Path(self.backup_config.backup_path) / f"{name}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # Nettoyer les anciennes sauvegardes
            self._cleanup_old_backups('.json')
            
            return True
            
        except Exception:
            return False
    
    def _load_json(self, name: str) -> Optional[Dict[str, Any]]:
        """Charge depuis le format JSON"""
        try:
            file_path = Path(self.backup_config.backup_path) / f"{name}.json"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception:
            return None
    
    def _save_pickle(self, name: str, data: Any) -> bool:
        """Sauvegarde en format Pickle"""
        try:
            file_path = Path(self.backup_config.backup_path) / f"{name}.pkl"
            
            with open(file_path, 'wb') as f:
                pickle.dump(data, f)
            
            self._cleanup_old_backups('.pkl')
            return True
            
        except Exception:
            return False
    
    def _load_pickle(self, name: str) -> Optional[Any]:
        """Charge depuis le format Pickle"""
        try:
            file_path = Path(self.backup_config.backup_path) / f"{name}.pkl"
            
            with open(file_path, 'rb') as f:
                return pickle.load(f)
                
        except Exception:
            return None
    
    def _save_sqlite(self, name: str, data: Dict[str, Any]) -> bool:
        """Sauvegarde en base de données SQLite"""
        # Placeholder pour implémentation future
        return False
    
    def _load_sqlite(self, name: str) -> Optional[Dict[str, Any]]:
        """Charge depuis la base de données SQLite"""
        # Placeholder pour implémentation future
        return None
    
    def _save_to_database(self, dashboard_data: DashboardData) -> None:
        """Sauvegarde les données du dashboard en base"""
        if not self._db_connection:
            return
        
        try:
            cursor = self._db_connection.cursor()
            
            # Insérer le snapshot
            cursor.execute('''
                INSERT INTO dashboard_snapshots 
                (timestamp, system_metrics, layer_metrics, tensor_grid_stats)
                VALUES (?, ?, ?, ?)
            ''', (
                dashboard_data.timestamp,
                json.dumps(dashboard_data.system_metrics),
                json.dumps(dashboard_data.layer_metrics),
                json.dumps(dashboard_data.tensor_grid_stats)
            ))
            
            # Insérer les tendances
            for metric_name, values in dashboard_data.performance_trends.items():
                if values:
                    cursor.execute('''
                        INSERT INTO performance_trends 
                        (metric_name, value, timestamp)
                        VALUES (?, ?, ?)
                    ''', (metric_name, values[-1], dashboard_data.timestamp))
            
            self._db_connection.commit()
            self._stats['db_records'] += 1
            
        except Exception as e:
            print(f"Failed to save to database: {e}")
    
    def _update_performance_trends(self, system_metrics: Dict[str, Any],
                                  layer_metrics: Dict[str, Any]) -> None:
        """Met à jour les tendances de performance"""
        # Métriques système
        for key, value in system_metrics.items():
            if isinstance(value, (int, float)):
                if key not in self._performance_trends:
                    self._performance_trends[key] = []
                
                self._performance_trends[key].append(value)
                
                # Limiter l'historique
                if len(self._performance_trends[key]) > 100:
                    self._performance_trends[key] = self._performance_trends[key][-50:]
        
        # Métriques des layers
        for layer, metrics in layer_metrics.items():
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    metric_key = f"{layer}_{key}"
                    
                    if metric_key not in self._performance_trends:
                        self._performance_trends[metric_key] = []
                    
                    self._performance_trends[metric_key].append(value)
                    
                    # Limiter l'historique
                    if len(self._performance_trends[metric_key]) > 100:
                        self._performance_trends[metric_key] = (
                            self._performance_trends[metric_key][-50:]
                        )
    
    def _calculate_trend(self, metric_name: str) -> str:
        """Calcule la tendance d'une métrique"""
        if metric_name not in self._performance_trends:
            return 'unknown'
        
        values = self._performance_trends[metric_name]
        
        if len(values) < 10:
            return 'insufficient_data'
        
        # Comparer la moyenne récente à la moyenne ancienne
        recent_avg = np.mean(values[-5:])
        older_avg = np.mean(values[-20:-5])
        
        if recent_avg > older_avg * 1.05:
            return 'improving'
        elif recent_avg < older_avg * 0.95:
            return 'degrading'
        else:
            return 'stable'
    
    def _cleanup_old_backups(self, extension: str) -> None:
        """Nettoie les anciennes sauvegardes"""
        try:
            backup_dir = Path(self.backup_config.backup_path)
            backup_files = list(backup_dir.glob(f"*{extension}"))
            
            # Trier par date de modification
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Supprimer les plus anciennes
            for file_to_delete in backup_files[self.backup_config.max_backups:]:
                file_to_delete.unlink()
                
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du gestionnaire"""
        with self._lock:
            stats = self._stats.copy()
            stats.update({
                'last_backup_time': self._last_backup_time,
                'time_since_last_backup': time.time() - self._last_backup_time,
                'dashboard_history_size': len(self._dashboard_history),
                'performance_trends_count': len(self._performance_trends),
                'backup_thread_running': (
                    self._backup_thread and self._backup_thread.is_alive()
                ),
                'configuration': {
                    'backup_frequency': self.backup_config.frequency.value,
                    'backup_format': self.backup_config.format.value,
                    'max_backups': self.backup_config.max_backups,
                    'dashboard_enabled': self.enable_dashboard
                }
            })
            return stats
    
    def shutdown(self) -> None:
        """Arrête proprement le gestionnaire"""
        # Arrêter le thread de sauvegarde
        if self._backup_thread:
            self._stop_backup.set()
            self._backup_thread.join(timeout=2.0)
        
        # Fermer la base de données
        if self._db_connection:
            self._db_connection.close()
