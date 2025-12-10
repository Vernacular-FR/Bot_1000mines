"""
S4 Solver - Orchestrateur hybride CSP/Monte Carlo/Neural

Interface publique pour la couche de résolution:
- HybridSolver: Orchestrateur principal coordonnant les moteurs
- TensorFrontier: Adaptateur TensorGrid → Solver
- CSPEngine: Moteur CSP exact avec segmentation
"""

from .hybrid_solver import HybridSolver, SolverStrategy, SolverAction, SolverResult
from .tensor_frontier import TensorFrontier, FrontierZone, FrontierZoneType, SolverContext
from .csp.csp_engine import CSPEngine, CSPResult, CSPSolution

__version__ = "2.0.0"
__all__ = [
    # Classes principales
    'HybridSolver',
    'TensorFrontier', 
    'CSPEngine',
    
    # Types et énumérations
    'SolverStrategy',
    'FrontierZoneType',
    'CSPResult',
    
    # Structures de données
    'SolverAction',
    'SolverResult',
    'FrontierZone',
    'SolverContext',
    'CSPSolution',
]
