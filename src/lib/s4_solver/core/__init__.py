"""Core building blocks for the s4 solver (segmentation, CSP, adapters, etc.)."""

from .segmentation import Component, Segmentation, Zone, FrontierViewProtocol  # noqa: F401
from .csp_solver import CSPSolver, Solution  # noqa: F401
from .views import SolverFrontierView  # noqa: F401
