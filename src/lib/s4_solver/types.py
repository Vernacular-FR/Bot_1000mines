"""Types pour le module s4_solver."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Any

from src.lib.s3_storage.types import Coord, GridCell, StorageUpsert


class ActionType(str, Enum):
    """Type d'action décidée par le solver."""
    SAFE = "SAFE"
    FLAG = "FLAG"
    GUESS = "GUESS"


# Alias pour compatibilité overlay
SolverActionType = ActionType


@dataclass
class SolverAction:
    """Action décidée par le solver."""
    coord: Coord
    action: ActionType
    confidence: float
    reasoning: str = ""


@dataclass
class SolverInput:
    """Input pour le solver."""
    cells: Dict[Coord, GridCell]
    frontier: Set[Coord]
    active_set: Set[Coord]


@dataclass
class SolverOutput:
    """Output du solver."""
    actions: List[SolverAction]
    reducer_actions: List[SolverAction] | None = None
    upsert: Optional[StorageUpsert] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Snapshots pour progression UI (3 étapes du solver)
    snapshot_pre_solver: Optional[Dict[Coord, GridCell]] = None  # Avant pipeline1 (état brut storage)
    snapshot_post_pipeline1: Optional[Dict[Coord, GridCell]] = None  # Après StatusAnalyzer, avant CSP
    snapshot_post_solver: Optional[Dict[Coord, GridCell]] = None  # Après CSP + ActionMapper (état final)
    
    @property
    def safe_count(self) -> int:
        return sum(1 for a in self.actions if a.action == ActionType.SAFE)
    
    @property
    def flag_count(self) -> int:
        return sum(1 for a in self.actions if a.action == ActionType.FLAG)


@dataclass
class PropagationResult:
    """Résultat de la propagation contrainte."""
    safe_cells: Set[Coord]
    flag_cells: Set[Coord]
    solved_cells: Set[Coord]
    iterations: int
    reasoning: str
