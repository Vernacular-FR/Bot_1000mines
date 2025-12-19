"""Module s4_solver : résolution du démineur (boîte noire).

API publique :
    solve(storage, overlay_ctx=None, base_image=None) → SolverOutput

Structure interne (non exposée) :
- s4a_status_analyzer/ : Classification topologique et gestion des statuts
- s4b_csp_solver/ : Logique CSP (reducer + backtracking)
- s4c_overlays/ : Overlays de debug
"""

# Façade principale (seule API publique)
from .solver import solve

# Types pour le typage
from .types import SolverOutput, SolverAction, ActionType

__all__ = [
    "solve",
    "SolverOutput",
    "SolverAction",
    "ActionType",
]
