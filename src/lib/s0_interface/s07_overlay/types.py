"""
Types pour le système d'overlay UI.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional


class OverlayType(str, Enum):
    """Types d'overlays disponibles."""
    OFF = "off"
    FRONTIER = "frontier"
    ACTIONS = "actions"
    STATUS = "status"


class FocusLevel(str, Enum):
    """Niveaux de focus pour les cellules."""
    TO_PROCESS = "TO_PROCESS"
    PROCESSED = "PROCESSED"
    TO_REDUCE = "TO_REDUCE"
    REDUCED = "REDUCED"


class ActionType(str, Enum):
    """Types d'actions du solver."""
    SAFE = "SAFE"
    FLAG = "FLAG"
    GUESS = "GUESS"


@dataclass
class CellOverlayData:
    """Données d'affichage pour une cellule."""
    col: int
    row: int
    status: Optional[str] = None
    focus_level: Optional[str] = None


@dataclass
class ActionOverlayData:
    """Données d'affichage pour une action."""
    col: int
    row: int
    type: str  # SAFE, FLAG, GUESS
    confidence: Optional[float] = None


@dataclass
class OverlayData:
    """
    Conteneur pour les données d'overlay à transmettre au JavaScript.
    """
    overlay_type: OverlayType
    cells: Optional[List[CellOverlayData]] = None
    actions: Optional[List[ActionOverlayData]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour JSON."""
        result = {}
        
        if self.cells:
            result['cells'] = [
                {
                    'col': cell.col,
                    'row': cell.row,
                    'status': cell.status,
                    'focus_level': cell.focus_level,
                }
                for cell in self.cells
            ]
        
        if self.actions:
            result['actions'] = [
                {
                    'col': action.col,
                    'row': action.row,
                    'type': action.type,
                    'confidence': action.confidence,
                }
                for action in self.actions
            ]
        
        return result


@dataclass
class OverlayConfig:
    """Configuration de l'overlay UI."""
    enabled: bool = True
    default_overlay: OverlayType = OverlayType.OFF
    auto_update: bool = True
    cell_size: int = 24
    cell_border: int = 1
