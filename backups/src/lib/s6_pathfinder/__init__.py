"""
S6 Pathfinder - Planification de trajectoire et viewport (S6)

Interface publique pour la couche de pathfinding:
- DensityAnalyzer: Analyse de densité TensorGrid
- PathPlanner: Génération de vecteurs de mouvement
- ViewportScheduler: Ordonnancement des zones hors-champ
"""

from .s61_density_analyzer import DensityAnalyzer, DensityMap, RegionDensity, DensityMetric
from .s62_path_planner import PathPlanner, MovementVector, PathPlan, MovementStrategy, PathPriority
from .s63_viewport_scheduler import ViewportScheduler, ViewportTask, CaptureRequest, VisitStatus, CaptureTrigger

__version__ = "1.0.0"
__all__ = [
    # Classes principales
    'DensityAnalyzer',
    'PathPlanner',
    'ViewportScheduler',
    
    # Types et énumérations
    'DensityMetric',
    'MovementStrategy', 
    'PathPriority',
    'VisitStatus',
    'CaptureTrigger',
    
    # Structures de données
    'DensityMap',
    'RegionDensity',
    'MovementVector',
    'PathPlan',
    'ViewportTask',
    'CaptureRequest',
]