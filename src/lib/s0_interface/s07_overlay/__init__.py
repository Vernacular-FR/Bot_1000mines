"""
Overlay UI pour le bot 1000mines.
"""

from .overlay_injector import OverlayInjector, create_overlay_injector
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
    'OverlayInjector',
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
    'create_overlay_injector',
]
