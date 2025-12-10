"""
S3 Tensor Core - Fondation partagée pour les tenseurs et indices

Composants principaux:
- TensorGrid: Grille tensorielle multi-tenseur avec zero-copy
- HintCache: Cache d'indices pour communication inter-couches
- TraceRecorder: Enregistreur de traces centralisé
"""

from .tensor_grid import TensorGrid, GridBounds, CellSymbol
from .hint_cache import HintCache, HintType, HintEvent
from .trace_recorder import TraceRecorder, TraceType, TraceEvent

__version__ = "1.0.0"
__all__ = [
    # Classes principales
    'TensorGrid',
    'HintCache', 
    'TraceRecorder',
    
    # Types et énumérations
    'GridBounds',
    'CellSymbol',
    'HintType',
    'HintEvent',
    'TraceType',
    'TraceEvent',
]