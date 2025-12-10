"""
Ops - Observabilité et persistance pour tous les layers S0-S6

Interface publique pour la couche d'observabilité:
- MetricsCollector: Collection de KPI et alertes
- AsyncLogger: Logging haute performance asynchrone
- PersistenceManager: Sauvegarde/restore et dashboards
"""

from .metrics import (
    MetricsCollector, MetricType, LayerType, MetricValue, LayerMetrics
)
from .async_logger import (
    AsyncLogger, LogLevel, LogFormat, LogEntry, AsyncLogHandler
)
from .persistence import (
    PersistenceManager, PersistenceFormat, BackupFrequency, 
    BackupConfig, DashboardData
)

__version__ = "1.0.0"
__all__ = [
    # Classes principales
    'MetricsCollector',
    'AsyncLogger',
    'PersistenceManager',
    
    # Types et énumérations
    'MetricType',
    'LayerType',
    'LogLevel',
    'LogFormat',
    'PersistenceFormat',
    'BackupFrequency',
    
    # Structures de données
    'MetricValue',
    'LayerMetrics',
    'LogEntry',
    'AsyncLogHandler',
    'BackupConfig',
    'DashboardData',
]