"""Sous-module s4b_csp_solver : Logique de résolution."""

from .csp_manager import solve, solve_from_cells, CspManager
from .reducer import IterativePropagator
from .segmentation import Segmentation, Zone, Component
from .csp import CSPSolver, Solution
from .frontier_view import SolverFrontierView

__all__ = [
    "solve",
    "solve_from_cells",
    "CspManager",
    "IterativePropagator",
    "Segmentation",
    "Zone",
    "Component",
    "CSPSolver",
    "Solution",
    "SolverFrontierView",
]
