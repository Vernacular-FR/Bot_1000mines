"""
Overlay UI pour le bot 1000mines.
"""

from .types import OverlayType, OverlayData, CellOverlayData, ActionOverlayData

# Nouveau système UI temps réel
from .ui_controller import (
    UIController,
    UIOverlayType,
    StatusCellData,
    ActionCellData,
    ProbabilityCellData,
    get_ui_controller,
)

__all__ = [
    'OverlayType',
    'OverlayData',
    'CellOverlayData',
    'ActionOverlayData',
    'UIController',
    'UIOverlayType',
    'StatusCellData',
    'ActionCellData',
    'ProbabilityCellData',
    'get_ui_controller',
]
