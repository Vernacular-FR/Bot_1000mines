"""
S0 Navigation - Interface d'interaction navigateur (S0)

Interface publique pour la couche de navigation:
- NavigationPrimitives: Interface d'interaction browser
- BrowserNavigation: Implémentation Selenium avec retries
- CoordinateConverter: Transformations grille ↔ écran
- InterfaceDetector: Détection et masquage UI
"""

from .s01_primitives import (
    NavigationPrimitives, ActionResult, NavigationStats,
    BrowserNavigation, StubNavigation
)
from .s02_interface_detector import (
    InterfaceDetector, UIElement, InterfaceMask, UIElementType
)
from .s03_coordinate_converter import (
    CoordinateConverter, Point2D
)

__version__ = "1.0.0"
__all__ = [
    # Interfaces et classes principales
    'NavigationPrimitives',
    'BrowserNavigation',
    'StubNavigation',
    'CoordinateConverter',
    'InterfaceDetector',
    
    # Types et énumérations
    'ActionResult',
    'UIElementType',
    
    # Structures de données
    'NavigationStats',
    'UIElement',
    'InterfaceMask',
    'Point2D',
]
