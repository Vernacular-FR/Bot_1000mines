"""Module s4_solver : Résolution du démineur (reducer + CSP)."""

from .types import SolverInput, SolverOutput, SolverAction, ActionType, SolverStats
from .solver import solve, Solver
from .reducer import FrontierReducer
from .csp import CspSolver

__all__ = [
    # Types
    "SolverInput",
    "SolverOutput",
    "SolverAction",
    "ActionType",
    "SolverStats",
    # Solver
    "solve",
    "Solver",
    # Composants
    "FrontierReducer",
    "CspSolver",
]
