"""
Solver Minesweeper - Module de résolution autonome

Ce module contient tous les composants pour résoudre les grilles de Minesweeper
à partir des screenshots dans temp/screenshots/zones/.

Architecture:
- core/ : Orchestrateur et gestion d'état
- csp/ : Solveur CSP
- visualization/ : Génération d'overlays visuels
"""

# Imports retardés pour éviter les erreurs de dépendances circulaires
from src.lib.s3_tensor.grid_state import GamePersistence, GridDB

__version__ = "1.0.0"
__all__ = ["GamePersistence", "GridDB"]
