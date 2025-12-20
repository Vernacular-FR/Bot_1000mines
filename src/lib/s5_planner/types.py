"""Types pour le module s5_planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict

from src.lib.s3_storage.types import Coord, GridCell
from src.lib.s0_coordinates.types import ScreenPoint, GridBounds
from src.lib.s4_solver.types import SolverAction, ActionType
from src.lib.s0_browser.game_info import GameInfo


@dataclass
class PlannedAction:
    """Action planifiée avec coordonnées écran."""
    coord: Coord
    action: ActionType
    screen_point: Optional[ScreenPoint] = None
    priority: int = 0
    confidence: float = 1.0
    reasoning: str = ""


@dataclass
class PlannerInput:
    """Input pour le planner."""
    actions: List[SolverAction]
    game_info: Optional[GameInfo] = None
    snapshot: Optional[Dict[Coord, GridCell]] = None
    grid_bounds: Optional[GridBounds] = None
    is_exploring: bool = False
    force_exploration: bool = False
    iteration: int = 0


@dataclass
class ExecutionPlan:
    """Plan d'exécution."""
    actions: List[PlannedAction]
    estimated_time: float = 0.0
    post_delay: float = 0.0
    
    @property
    def action_count(self) -> int:
        return len(self.actions)
