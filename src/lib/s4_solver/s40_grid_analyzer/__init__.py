"""Core building blocks for the s4 solver (segmentation, CSP, adapters, etc.)."""

from src.lib.s4_solver.s43_csp_solver.segmentation import (  # noqa: F401
    Component,
    Segmentation,
    Zone,
    FrontierViewProtocol,
)
from src.lib.s4_solver.s43_csp_solver.csp_solver import CSPSolver, Solution  # noqa: F401
from .grid_extractor import SolverFrontierView  # noqa: F401
