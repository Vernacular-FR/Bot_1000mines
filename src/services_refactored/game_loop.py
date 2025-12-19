"""Game loop : pipeline principal du bot."""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import time

from .session_service import Session, get_current_session

from src.lib.s0_coordinates.types import GridBounds
from src.lib.s1_capture import capture_zone, CaptureInput
from src.lib.s2_vision import analyze, VisionInput
from src.lib.s4_solver import solve, SolverInput
from src.lib.s4_solver.types import GridCell as SolverGridCell
from src.lib.s5_planner import plan, PlannerInput
from src.lib.s6_executor import execute, ExecutorInput


@dataclass
class IterationResult:
    """Résultat d'une itération."""
    success: bool
    actions_executed: int
    duration: float
    metadata: Dict[str, Any]


class GameLoop:
    """Boucle de jeu principale."""

    def __init__(self, session: Session):
        self.session = session
        self.iteration_count = 0
        self.total_actions = 0

    def run_iteration(self) -> IterationResult:
        """Exécute une itération du pipeline."""
        start_time = time.time()
        self.iteration_count += 1

        try:
            # 1. Obtenir les bounds du viewport
            viewport_info = self.session.viewport.get_viewport_bounds()
            if not viewport_info:
                return IterationResult(
                    success=False,
                    actions_executed=0,
                    duration=time.time() - start_time,
                    metadata={"error": "Impossible d'obtenir les bounds du viewport"},
                )

            bounds = viewport_info.grid_bounds

            # 2. Capture
            # TODO: Implémenter la capture complète du viewport
            # Pour l'instant, on utilise un placeholder
            
            # 3. Vision
            # TODO: Implémenter l'analyse vision
            
            # 4. Storage update
            # TODO: Mettre à jour le storage avec les résultats vision
            
            # 5. Solver
            # TODO: Résoudre avec les données du storage
            
            # 6. Planner
            # TODO: Planifier les actions
            
            # 7. Executor
            # TODO: Exécuter les actions

            duration = time.time() - start_time
            
            return IterationResult(
                success=True,
                actions_executed=0,
                duration=duration,
                metadata={
                    "iteration": self.iteration_count,
                    "bounds": bounds.to_tuple() if bounds else None,
                },
            )

        except Exception as e:
            return IterationResult(
                success=False,
                actions_executed=0,
                duration=time.time() - start_time,
                metadata={"error": str(e)},
            )

    def run(self, max_iterations: int = 100, stop_on_error: bool = False) -> Dict[str, Any]:
        """Exécute la boucle de jeu complète."""
        results = []
        
        for _ in range(max_iterations):
            result = self.run_iteration()
            results.append(result)
            
            if not result.success and stop_on_error:
                break
            
            if result.actions_executed == 0:
                # Pas d'actions possibles, probablement fin de partie
                break

        return {
            "iterations": len(results),
            "total_actions": self.total_actions,
            "success": all(r.success for r in results),
        }


# === API fonctionnelle ===

def run_iteration(session: Optional[Session] = None) -> IterationResult:
    """Exécute une itération du pipeline."""
    session = session or get_current_session()
    if not session:
        return IterationResult(
            success=False,
            actions_executed=0,
            duration=0.0,
            metadata={"error": "Pas de session active"},
        )
    
    loop = GameLoop(session)
    return loop.run_iteration()


def run_game(
    session: Optional[Session] = None,
    max_iterations: int = 100,
) -> Dict[str, Any]:
    """Exécute une partie complète."""
    session = session or get_current_session()
    if not session:
        return {"error": "Pas de session active"}
    
    loop = GameLoop(session)
    return loop.run(max_iterations)
