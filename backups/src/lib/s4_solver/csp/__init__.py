"""
S4 CSP Engine - Moteur de résolution par contraintes

Composants CSP pour le solveur hybride:
- CSPEngine: Moteur principal de résolution CSP
- CSPResult: Résultats de résolution CSP
- CSPSolution: Solutions CSP validées
"""

from .csp_engine import CSPEngine, CSPResult, CSPSolution
from .csp_constraints import CSPConstraint, ConstraintType
from .csp_variables import CSPVariable, VariableDomain

__version__ = "1.0.0"
__all__ = [
    # Classes principales
    'CSPEngine',
    'CSPResult', 
    'CSPSolution',
    
    # Contraintes et variables
    'CSPConstraint',
    'ConstraintType',
    'CSPVariable',
    'VariableDomain',
]
