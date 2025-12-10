"""
S2 Recognition - Reconnaissance de symboles et frontières (S2)

Interface publique pour la couche de reconnaissance:
- TemplateHierarchy: Hiérarchie de templates (color → variance → template)
- SmartMatcher: Scanner intelligent avec intégration frontier_mask
- FrontierExtractor: Extraction de frontières pour S4/S6
"""

from .s21_templates import (
    TemplateHierarchy, TemplateLevel, ColorSignature, TemplateMatch, CellTemplate
)
from .s22_matching import (
    SmartMatcher, MatchingStrategy, MatchingResult, BatchMatchingResult
)
from .s23_frontier import (
    FrontierExtractor, FrontierType, FrontierCell, FrontierExtractionResult
)

__version__ = "1.0.0"
__all__ = [
    # Classes principales
    'TemplateHierarchy',
    'SmartMatcher',
    'FrontierExtractor',
    
    # Types et énumérations
    'TemplateLevel',
    'MatchingStrategy',
    'FrontierType',
    
    # Structures de données
    'ColorSignature',
    'TemplateMatch',
    'CellTemplate',
    'MatchingResult',
    'BatchMatchingResult',
    'FrontierCell',
    'FrontierExtractionResult',
]
