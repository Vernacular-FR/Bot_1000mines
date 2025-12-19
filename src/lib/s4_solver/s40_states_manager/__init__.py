"""Core building blocks for the s4 solver (segmentation, CSP, adapters, etc.)."""

from src.lib.s4_solver.s42_csp_solver.s422_segmentation import (  # noqa: F401
    Component,
    Segmentation,
    Zone,
    FrontierViewProtocol,
)
from src.lib.s4_solver.s42_csp_solver.s424_csp_solver import CSPSolver, Solution  # noqa: F401
from .grid_extractor import SolverFrontierView  # noqa: F401
