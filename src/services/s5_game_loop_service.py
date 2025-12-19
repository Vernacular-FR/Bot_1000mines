"""
Service de boucle de jeu pour le démineur.
Orchestre les itérations en utilisant SingleIterationService.
"""

import time
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

# Imports du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import CELL_SIZE

# Imports des services
from .s1_session_setup_service import SessionSetupService
from .s1_zone_capture_service import ZoneCaptureService
from .s2_vision_analysis_service import VisionAnalysisService
from .s3_game_solver_service import GameSolverServiceV2
from .s4_action_executor_service import ActionExecutorService
from .s5_single_iteration_service import SingleIterationService, IterationResult
from src.lib.s3_storage.controller import StorageController
from src.lib.s4_solver.s40_states_manager.state_analyzer import StateAnalyzer
from src.lib.s5_actionplanner.controller import ActionPlannerController
from src.lib.s6_action.controller import convert_pathfinder_plan_to_game_actions
from src.lib.s4_solver.facade import SolverAction, SolverActionType


class GameState(Enum):
    """États possibles du jeu"""
    PLAYING = "playing"      # Partie en cours
    WON = "won"             # Partie gagnée
    LOST = "lost"           # Partie perdue
    ERROR = "error"         # Erreur technique
    TIMEOUT = "timeout"     # Timeout atteint
    NO_ACTIONS = "no_actions"  # Plus d'actions possibles


class GameResult:
    """Résultat d'une partie complète"""
    def __init__(self):
        self.success: bool = False
        self.final_state: Optional[GameState] = None
        self.total_iterations: int = 0
        self.iterations: int = 0  # Alias pour compatibilité
        self.actions_executed: int = 0
        self.errors: List[str] = []


class GameLoopService:
    """
    Service qui orchestre la boucle de jeu complète.
    Utilise SingleIterationService pour chaque passe.
    """

    def __init__(
        self,
        interface=None,
        storage=None,
        capture_service=None,
        vision_service=None,
        solver_service=None,
        state_analyzer=None,
        game_paths: Dict[str, str] = None,
        game_id: str = None,
        game_base_path: str = None,
        overlay_enabled: bool = True,
        max_iterations: int = 500,
        iteration_delay: float = 1.0,
        # Paramètres de compatibilité (ancienne interface)
        session_service=None,
        iteration_timeout: float = 60.0,
        delay_between_iterations: float = 1.0,
        execute_actions: bool = True,
    ):
        # Compatibilité : initialiser comme l'ancienne version
        if session_service:
            self.session_service = session_service
            self.driver = session_service.get_driver()
            self.coordinate_converter = session_service.get_coordinate_converter()
            
            # Utiliser le gestionnaire centralisé de session
            self.game_session = {
                "state": session_service.session_state,
                "storage": session_service.session_storage,
            }
            
            self.game_id = self.game_session['state'].game_id
            self.iteration_num = self.game_session['state'].iteration_num
            
            # Initialiser les services avec les chemins de la partie
            storage = self.game_session['storage'].ensure_storage_ready(self.game_session['state'], create_metadata=False)
            self.game_paths = storage['paths']
            self.game_base_path = storage['base_path']
            
            # Initialiser les services
            self.interface = session_service.get_interface()
            self.capture_service = ZoneCaptureService(interface=self.interface)
            export_root = Path(self.game_base_path) if overlay_enabled else None
            
            # Publier le contexte de session
            from src.lib.s3_storage.s30_session_context import set_session_context
            set_session_context(
                game_id=self.game_id,
                iteration=self.iteration_num or 0,
                export_root=str(export_root) if export_root else "",
                overlay_enabled=overlay_enabled,
            )
            
            self.storage = StorageController()
            self.vision_service = VisionAnalysisService()
            self.solver_service = GameSolverServiceV2(storage=self.storage)
            self.state_analyzer = StateAnalyzer()
        else:
            # Interface directe (nouvelle version)
            self.interface = interface
            self.storage = storage
            self.capture_service = capture_service
            self.vision_service = vision_service
            self.solver_service = solver_service
            self.state_analyzer = state_analyzer
            self.game_paths = game_paths
            self.game_id = game_id
            self.game_base_path = game_base_path
        
        self.overlay_enabled = overlay_enabled
        self.max_iterations = max_iterations
        self.iteration_delay = delay_between_iterations or iteration_delay
        
        # Services internes
        self.action_executor = ActionExecutorService(self.coordinate_converter, self.driver)
        self.action_planner = ActionPlannerController()
        
        # Service d'itération unique
        self.single_iteration = SingleIterationService(
            interface=self.interface,
            storage=self.storage,
            capture_service=self.capture_service,
            vision_service=self.vision_service,
            solver_service=self.solver_service,
            state_analyzer=self.state_analyzer,
            game_paths=self.game_paths,
            game_id=self.game_id,
            game_base_path=self.game_base_path,
            overlay_enabled=self.overlay_enabled,
        )
        
        # Statistiques
        self.stats = {
            'iterations': 0,
            'actions_executed': 0,
            'errors': [],
            'start_time': None,
            'end_time': None,
        }

    def play_game(self) -> GameResult:
        """
        Lance la boucle de jeu complète.
        
        Returns:
            GameResult avec le déroulement de la partie
        """
        result = GameResult()
        self.stats['start_time'] = time.time()
        
        print(f"[GAME] Démarrage d'une nouvelle partie (Max itérations: {self.max_iterations})")
        print(f"[GAME] ID de partie: {self.game_id}")
        print(f"[GAME] Dossier de sauvegarde: {self.game_base_path}")
        print("[INFO] Statistiques GameLoopService remises à zéro")
        
        try:
            for iteration in range(1, self.max_iterations + 1):
                print(f"\n--- Itération {iteration} ---")
                
                # Exécuter une seule itération
                iter_result = self.single_iteration.execute_single_pass(iteration)
                
                if not iter_result.success:
                    print(f"[ERREUR] Échec de la passe {iteration}: {iter_result.message}")
                    result.errors.append(iter_result.message)
                    result.final_state = GameState.ERROR
                    break
                
                # Planifier et exécuter les actions si trouvées
                if iter_result.actions:
                    # Planification
                    plan = self.action_planner.plan(iter_result.actions)
                    
                    # Conversion en actions jeu
                    game_actions = convert_pathfinder_plan_to_game_actions(plan)
                    
                    # Exécution
                    exec_result = self.action_executor.execute_actions(game_actions)
                    
                    if exec_result['success']:
                        print(f"[ACTION] Exécution terminée: {exec_result['executed_count']}/{len(game_actions)} actions réussies en {exec_result['duration']:.2f}s")
                        result.actions_executed += exec_result['executed_count']
                        self.stats['actions_executed'] = result.actions_executed
                    else:
                        print(f"[ERREUR] Échec de l'exécution: {exec_result['error']}")
                        result.errors.append(exec_result['error'])
                        result.final_state = GameState.ERROR
                        break
                else:
                    print(f"[PASS] Passe {iteration} terminée: Aucune action trouvée par le solveur")
                    result.final_state = GameState.NO_ACTIONS
                    break
                
                # Délai entre les itérations
                if self.iteration_delay > 0:
                    time.sleep(self.iteration_delay)
                
                result.total_iterations = iteration
                result.iterations = iteration  # Alias pour compatibilité
                self.stats['iterations'] = iteration
                
        except KeyboardInterrupt:
            print("\n[GAME] Partie interrompue par l'utilisateur")
            result.final_state = GameState.ERROR
            result.errors.append("Interruption utilisateur")
            
        except Exception as e:
            print(f"\n[ERREUR] Erreur inattendue: {e}")
            result.final_state = GameState.ERROR
            result.errors.append(str(e))
            
        finally:
            self.stats['end_time'] = time.time()
            duration = self.stats['end_time'] - self.stats['start_time']
            
            print(f"\n[GAME] Fin de partie détectée: {result.final_state.value if result.final_state else 'unknown'}")
            print(f"[GAME] success={result.success} final_state={result.final_state.value if result.final_state else 'unknown'} "
                  f"iterations={result.total_iterations} actions_executed={result.actions_executed}")
            print(f"[SESSION] Partie terminée. Appuyez sur Entrée pour fermer le navigateur…")
            
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de la partie."""
        stats = self.stats.copy()
        if stats['start_time'] and stats['end_time']:
            stats['duration'] = stats['end_time'] - stats['start_time']
        return stats
