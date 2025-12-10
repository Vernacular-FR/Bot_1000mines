"""
S5 Actionneur - Orchestrateur d'actions et exécution (S5)

Interface publique pour la couche d'action:
- ActionQueue: File prioritaire avec clustering spatial
- ActionExecutor: Traduction actions → primitives S0
- ActionLogger: Journalisation et mise à jour TensorGrid
"""

from .s51_action_queue import ActionQueue, QueuedAction, ActionStatus, ActionPriority
from .s52_action_executor import ActionExecutor, ExecutionReport, ExecutionResult, NavigationPrimitives
from .s53_action_logger import ActionLogger, ActionTrace, ZoneStatus, ZoneUpdate

# Type aliases for backward compatibility with adapters
GameAction = QueuedAction
ActionType = ActionStatus
ActionResult = ExecutionResult

__version__ = "1.0.0"
__all__ = [
    # Classes principales
    'ActionQueue',
    'ActionExecutor', 
    'ActionLogger',
    
    # Types et énumérations
    'ActionStatus',
    'ActionPriority',
    'ExecutionResult',
    'ZoneStatus',
    
    # Structures de données
    'QueuedAction',
    'ExecutionReport',
    'ActionTrace',
    'ZoneUpdate',
    
    # Interfaces
    'NavigationPrimitives',
    
    # Type aliases for backward compatibility
    'GameAction',
    'ActionType', 
    'ActionResult',
]