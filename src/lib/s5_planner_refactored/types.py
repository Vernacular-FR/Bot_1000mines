"""Types pour le module s5_planner."""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Any, Dict

from src.lib.s0_coordinates.types import Coord, ScreenPoint, GridBounds
from src.lib.s4_solver.types import SolverAction, ActionType


@dataclass
class PlannedAction:
    """Action planifiée avec coordonnées écran."""
    coord: Coord
    action: ActionType
    screen_point: ScreenPoint
    priority: int = 0
    confidence: float = 1.0
    
    def to_tuple(self) -> Tuple[int, int]:
        return (self.coord.row, self.coord.col)


@dataclass
class PlannerInput:
    """Input pour le planner."""
    actions: List[SolverAction]
    grid_bounds: GridBounds
    viewport_bounds: Optional[GridBounds] = None
    config: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionPlan:
    """Plan d'exécution ordonné."""
    actions: List[PlannedAction]
    estimated_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def action_count(self) -> int:
        return len(self.actions)
    
    @property
    def has_actions(self) -> bool:
        return len(self.actions) > 0
    
    def get_by_type(self, action_type: ActionType) -> List[PlannedAction]:
        return [a for a in self.actions if a.action == action_type]
    
    @property
    def click_actions(self) -> List[PlannedAction]:
        return self.get_by_type(ActionType.CLICK)
    
    @property
    def flag_actions(self) -> List[PlannedAction]:
        return self.get_by_type(ActionType.FLAG)
