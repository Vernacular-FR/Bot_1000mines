from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple

from src.lib.s4_solver.facade import SolverAction


@dataclass
class PathfinderAction:
    type: str  # "click" | "flag" | "guess"
    cell: Tuple[int, int]
    confidence: float
    reasoning: str


@dataclass
class PathfinderPlan:
    actions: List[PathfinderAction]
    overlay_path: Optional[str] = None


class PathfinderApi(Protocol):
    def plan_actions(self, actions: List[SolverAction]) -> PathfinderPlan:
        ...
