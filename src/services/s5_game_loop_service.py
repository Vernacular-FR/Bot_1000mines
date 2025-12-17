"""
Service de boucle de jeu complète pour le démineur.
Orchestre le cycle analyse → résolution → exécution → répétition en utilisant les services existants.
"""

import time
import os
import sys
import shutil
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

# Imports du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import CELL_SIZE
from src.lib.s0_interface.s03_Coordonate_system import CoordinateConverter, CanvasLocator
from src.lib.s1_capture.s11_canvas_capture import CanvasCaptureBackend

# Imports des services
from .s1_session_setup_service import SessionSetupService
from .s1_zone_capture_service import ZoneCaptureService
from .s2_vision_analysis_service import VisionAnalysisService
from .s3_game_solver_service import GameSolverServiceV2
from .s4_action_executor_service import ActionExecutorService
from src.lib.s4_solver.s40_states_classifier.state_analyzer import StateAnalyzer
from src.lib.s5_actionplanner.controller import ActionPlannerController
from src.lib.s6_action.controller import convert_pathfinder_plan_to_game_actions
from src.lib.s4_solver.facade import SolverAction, SolverActionType
from src.lib.s2_vision.s23_vision_to_storage import matches_to_upsert
from src.lib.s3_storage.controller import StorageController
from src.lib.s3_storage.s30_session_context import (
    set_session_context,
    update_capture_path,
    update_capture_metadata,
)

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
        self.success = False
        self.final_state = GameState.PLAYING
        self.total_time = 0.0
        self.iterations = 0
        self.actions_executed = 0
        self.message = ""
        self.stats = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            'success': self.success,
            'final_state': self.final_state.value,
            'total_time': self.total_time,
            'iterations': self.iterations,
            'actions_executed': self.actions_executed,
            'message': self.message,
            'stats': self.stats
        }

class GameLoopService:
    def __init__(
        self,
        session_service: SessionSetupService,
        max_iterations: int = 100,
        iteration_timeout: float = 60.0,
        delay_between_iterations: float = 1.0,
        overlay_enabled: bool = False,
        execute_actions: bool = True,
        game_session=None,
    ):
        """
        Initialise le service de boucle de jeu.

        Args:
            session_service: Service de session configuré
            max_iterations: Nombre max d'itérations par partie
            iteration_timeout: Timeout par itération en secondes
            delay_between_iterations: Délai entre les itérations
            game_session: Instance du gestionnaire de session (optionnel)
        """
        self.session_service = session_service
        self.driver = session_service.get_driver()
        # On récupère le coordinate converter via le session service
        try:
            self.coordinate_converter = session_service.get_coordinate_converter()
        except AttributeError:
            self.coordinate_converter = None
            
        self.max_iterations = max_iterations
        self.overlay_enabled = overlay_enabled
        self.execute_actions = execute_actions
        
        # Utiliser le gestionnaire centralisé de session fourni
        if game_session is None:
            # Construire à partir du SessionSetupService existant
            self.game_session = {
                "state": session_service.session_state,
                "storage": session_service.session_storage,
            }
        else:
            self.game_session = game_session
            
        self.game_id = self.game_session['state'].game_id
        self.iteration_num = self.game_session['state'].iteration_num
        
        # Vérifier qu'une partie est bien initialisée
        if not self.game_id:
            raise ValueError("GameLoopService nécessite une partie initialisée.")
        
        # Initialiser les services avec les chemins de la partie
        storage = self.game_session['storage'].ensure_storage_ready(self.game_session['state'], create_metadata=False)
        self.game_paths = storage['paths']
        self.game_base_path = storage['base_path']
        # Initialiser les services (pipeline minimal vision -> storage -> solver V2)
        self.interface = session_service.get_interface()
        self.capture_service = ZoneCaptureService(interface=self.interface)
        export_root = Path(self.game_base_path) if self.overlay_enabled else None
        # Publier le contexte de session (consommé par les modules)
        set_session_context(
            game_id=self.game_id,
            iteration=self.iteration_num or 0,
            export_root=str(export_root) if export_root else "",
            overlay_enabled=self.overlay_enabled,
        )
        self.vision_service = VisionAnalysisService()
        self.storage = StorageController()
        self.solver_service = GameSolverServiceV2(storage=self.storage)
        self.action_service = (
            ActionExecutorService(self.coordinate_converter, self.driver)
            if self.execute_actions and self.coordinate_converter
            else None
        )
        self.action_planner = ActionPlannerController()
        
        # Instance réutilisable de StateAnalyzer
        self.state_analyzer = StateAnalyzer()
        
        # État du jeu
        self.current_game_state = GameState.PLAYING
        self.total_actions_executed = 0
        self.game_start_time = time.time()
        self.stop_requested = False  # Ajout de l'attribut manquant
        self.delay_between_iterations = delay_between_iterations  # Ajout de l'attribut
        
        # Statistiques
        self.stats = {
            'iterations_completed': 0,
            'actions_per_iteration': [],
            'analysis_time_per_iteration': [],
            'solver_time_per_iteration': [],
            'total_cells_processed': 0,
            'total_safe_actions': 0,
            'total_flag_actions': 0
        }

    def execute_single_pass(self, iteration_num: int = None) -> Dict[str, Any]:
        """
        Exécute une seule passe complète : Capture -> Analyse -> Solver
        (sans exécution d'actions si execute_actions=False)
        Utilise le gestionnaire centralisé de session pour le numéro d'itération.
        
        Args:
            iteration_num: Numéro de l'itération (si None, utilise la session courante)
        
        Returns:
            Dict: Résultat de la passe avec succès, actions exécutées, état du jeu, etc.
        """
        # Utiliser le numéro d'itération de la session si non fourni
        if iteration_num is None:
            iteration_num = self.game_session['state'].iteration_num
        iter_label = iteration_num if iteration_num is not None else 0
        # Publier le contexte courant (inclut l'itération à jour)
        export_root = Path(self.game_base_path) if self.overlay_enabled else None
        set_session_context(
            game_id=self.game_id,
            iteration=iter_label,
            export_root=str(export_root) if export_root else "",
            overlay_enabled=self.overlay_enabled,
        )
        # Import de secours pour éviter un NameError sur SolverActionType (rechargement)
        from src.lib.s4_solver.facade import SolverActionType as _SAT  # noqa: F401
        SolverActionType = _SAT  # ensure symbole local défini (NameError hotfix)
        
        try:
            pass_result = {
                'success': False,
                'actions_executed': 0,
                'game_state': self.current_game_state.value,
                'message': '',
                'files_saved': []
            }
            
            # 1. Capture de la zone de jeu via canvases
            print("[CAPTURE] Capture de la zone de jeu (canvases)...")
            locator = CanvasLocator(driver=self.interface.browser.get_driver())
            backend = CanvasCaptureBackend(self.interface.browser.get_driver())
            raw_dir = Path(self.game_paths["raw_canvases"])
            captures = self.capture_service.capture_canvas_tiles(
                locator=locator,
                backend=backend,
                out_dir=raw_dir,
                game_id=self.game_id,
            )
            if not captures:
                pass_result['message'] = "Aucune capture canvas effectuée"
                return pass_result

            grid_capture = self.capture_service.compose_from_canvas_tiles(
                captures=captures,
                grid_reference=self.interface.converter.grid_reference_point,
                save_dir=Path(self.game_paths["s1_canvas"]),
            )
            # Renommer la capture principale pour inclure game_id, itération et bounds
            try:
                sx, sy, ex, ey = grid_capture.grid_bounds
                target_name = f"{self.game_id}_iter{iter_label}_{sx}_{sy}_{ex}_{ey}.png"
                target_path = Path(self.game_paths["s1_canvas"]) / target_name
                current_path = Path(grid_capture.result.saved_path)
                if current_path != target_path:
                    if target_path.exists():
                        target_path.unlink()
                    current_path.rename(target_path)
                    grid_capture.result.saved_path = str(target_path)
            except Exception as exc:
                print(f"[CAPTURE] Impossible de renommer la capture principale: {exc}")

            pass_result['files_saved'].append(grid_capture.result.saved_path)
            # Publier la capture + métadonnées pour les modules aval (vision/solver/overlays)
            update_capture_metadata(
                grid_capture.result.saved_path,
                grid_capture.grid_bounds,
                grid_capture.cell_stride,
            )
            zone_bounds = grid_capture.grid_bounds

            # 2. Analyse de la grille
            print("[ANALYSE] Analyse de la grille...")
            analysis = self.vision_service.analyze_grid_capture(
                grid_capture,
                overlay=True,
            )
            if analysis.overlay_path:
                pass_result['files_saved'].append(str(analysis.overlay_path))

            # 3. Upsert storage puis state analyzer
            upsert = matches_to_upsert(grid_capture.grid_bounds, analysis.matches)
            self.storage.upsert(upsert)
            
            # 3b. State analyzer : promeut JUST_VISUALIZED -> ACTIVE/FRONTIER/SOLVED
            cells_snapshot = self.storage.get_cells(grid_capture.grid_bounds)
            state_upsert = self.state_analyzer.analyze_and_promote(cells_snapshot)
            if state_upsert.cells:
                self.storage.upsert(state_upsert)
            
            # Debug stockage
            active = self.storage.get_active()
            frontier = self.storage.get_frontier().coords
            print(f"[STORAGE] cells={len(upsert.cells)} active={len(active)} frontier={len(frontier)}")
            # Log rapide des premiers symboles
            sample_cells = list(upsert.cells.items())[:10]
            sample_desc = ", ".join([f"{coord}:{cell.raw_state.name}" for coord, cell in sample_cells])
            print(f"[STORAGE] échantillon cells: {sample_desc}")

            print("[SOLVEUR] Résolution du puzzle...")
            solve_result = self.solver_service.solve_snapshot()
            solver_actions = solve_result.get("actions", []) or []
            cleanup_actions = solve_result.get("cleanup_actions", []) or []
            reducer_actions = solve_result.get("reducer_actions", []) or []
            stats = solve_result.get("stats")
            segmentation = solve_result.get("segmentation")
            safe_cells = solve_result.get("safe_cells", [])
            total_flags = getattr(stats, "flag_cells", 0)
            total_safe = getattr(stats, "safe_cells", 0)
            print(
                f"[SOLVEUR] reduc={len(reducer_actions)} solver_actions={len(solver_actions)} cleanup_bonus={len(cleanup_actions)} "
                f"(safe={total_safe}, flags={total_flags}, "
                f"zones={getattr(stats, 'zones_analyzed', 0)}, comps={getattr(stats, 'components_solved', 0)})"
            )
            active_set = set(self.storage.get_active())
            frontier_set = set(self.storage.get_frontier().coords)

            if stats:
                self.stats['total_actions_executed'] = self.total_actions_executed
                # On ne compte pas les cleanups dans les métriques solver/CSP
                self.stats['actions_per_iteration'].append(len(solver_actions) + len(reducer_actions))
                self.stats['total_safe_actions'] += getattr(stats, "safe_cells", 0)
                self.stats['total_flag_actions'] += getattr(stats, "flag_cells", 0)

            # Détection simple d'état : aucune action + aucune case non résolue => victoire
            detected_state = self._detect_game_state(solver_actions, active_set, frontier_set)
            if detected_state != GameState.PLAYING:
                self.current_game_state = detected_state
                pass_result['game_state'] = detected_state.value
                pass_result['message'] = f"Partie terminée: {detected_state.value}"
                pass_result['success'] = True
                return pass_result

            # 4. (Optionnel) planification/exécution : désactivé si execute_actions=False
            if not self.execute_actions or not self.action_service:
                pass_result['success'] = True
                pass_result['actions_executed'] = 0
                pass_result['message'] = "Passe solver-only (aucune action exécutée)"
                return pass_result
            # Fusionner actions reducer + solver, puis prioriser les déterministes (CLICK/FLAG)
            all_actions = []
            if reducer_actions:
                all_actions.extend(reducer_actions)
            if solver_actions:
                all_actions.extend(solver_actions)
            # Cleanups sont un bonus après flags/safes
            all_actions.extend(cleanup_actions)
            deterministic_actions = [a for a in (reducer_actions + solver_actions) if a.type != SolverActionType.GUESS]
            deterministic_actions.extend(cleanup_actions)
            chosen_actions = deterministic_actions if deterministic_actions else all_actions
            print(
                f"[PLAN] total_actions={len(all_actions)} deterministes_sans_guess={len(deterministic_actions)} "
                f"choisis={len(chosen_actions)}"
            )

            path_plan = self.action_planner.plan(chosen_actions) if chosen_actions else None
            game_actions = []
            if path_plan:
                flags_actions = [a for a in path_plan.actions if a.type == "flag"]
                cleanup_actions = [a for a in path_plan.actions if a.type == "click" and "cleanup" in (a.reasoning or "")]
                safe_actions = [
                    a
                    for a in path_plan.actions
                    if a.type == "click" and "cleanup" not in (a.reasoning or "")
                ]
                # Comptes par cellule avant expansion
                flags_cells = {a.cell for a in flags_actions}
                cleanup_cells = {a.cell for a in cleanup_actions}
                safe_cells_plan = {a.cell for a in safe_actions}
                print(
                    f"[PLAN] cells flags={len(flags_cells)} safes={len(safe_cells_plan)} cleanup={len(cleanup_cells)}"
                )
                print(
                    f"[PLAN] actions expanded: flags={len(flags_actions)} safes={len(safe_actions)} cleanup={len(cleanup_actions)} total={len(path_plan.actions)}"
                )
                game_actions = convert_pathfinder_plan_to_game_actions(path_plan)

            if not game_actions:
                self.current_game_state = GameState.NO_ACTIONS
                pass_result['game_state'] = GameState.NO_ACTIONS.value
                pass_result['message'] = "Aucune action trouvée par le solveur"
                pass_result['success'] = True  # La passe a réussi
                return pass_result
        
            print(f"[EXÉCUTION] Exécution de {len(game_actions)} actions...")
            execution_result = self.action_service.execute_batch(game_actions)
            
            pass_result['success'] = True
            pass_result['actions_executed'] = execution_result['executed_count']
            pass_result['game_actions'] = game_actions
            return pass_result

        except Exception as exc:
            return {
                'success': False,
                'actions_executed': 0,
                'game_state': self.current_game_state.value if self.current_game_state else GameState.ERROR.value,
                'message': f"Erreur: {exc}",
                'files_saved': [],
            }

    def play_game(self) -> GameResult:
        """
        Joue une partie complète en boucle en utilisant execute_single_pass().
        Scénario 6 : boucle sur les passes jusqu'à fin de jeu ou limite atteinte.

        Returns:
            GameResult avec le résultat de la partie
        """
        print(f"[GAME] Démarrage d'une nouvelle partie (Max itérations: {self.max_iterations})")
        print(f"[GAME] ID de partie: {self.game_id}")
        print(f"[GAME] Dossier de sauvegarde: {self.game_base_path}")
        
        start_time = time.time()
        self.reset_stats()
        
        iteration = 0
        total_actions = 0
        
        while self._should_continue(self.current_game_state, iteration):
            # Incrémenter l'itération via le gestionnaire centralisé
            iteration = self.game_session['state'].increment_iteration()
            print(f"\n--- Itération {iteration} ---")
            
            # Exécuter une seule passe (utilise automatiquement le numéro de session)
            pass_result = self.execute_single_pass()
            
            if not pass_result['success']:
                print(f"[ERREUR] Échec de la passe {iteration}: {pass_result['message']}")
                # Si on est bloqué sur PLAYING malgré l'échec, c'est probablement une erreur technique
                if self.current_game_state == GameState.PLAYING:
                    self.current_game_state = GameState.ERROR
                break
            
            # Mettre à jour l'état du jeu depuis la passe
            try:
                # La passe retourne une string, on convertit en Enum
                new_state_value = pass_result['game_state']
                if new_state_value:
                    self.current_game_state = GameState(new_state_value)
            except ValueError:
                print(f"[ATTENTION] État de jeu inconnu retourné: {pass_result['game_state']}")
                
            total_actions += pass_result['actions_executed']
            print(f"[PASS] Passe {iteration} terminée: {pass_result['message']}")
            
            # Si la passe indique une fin de jeu (WON, LOST, NO_ACTIONS), arrêter
            if self.current_game_state in [GameState.WON, GameState.LOST, GameState.NO_ACTIONS]:
                print(f"[GAME] Fin de partie détectée: {self.current_game_state.value}")
                break
                
            # Pause pour laisser le jeu réagir aux actions (animations, chargement)
            time.sleep(self.delay_between_iterations)
        
        # Fin de partie
        total_time = time.time() - start_time
        self.stats['total_time'] = total_time
        self.stats['iterations'] = iteration
        self.stats['total_actions'] = total_actions
        
        result = GameResult()
        result.success = (self.current_game_state == GameState.WON)
        result.final_state = self.current_game_state
        result.total_time = total_time
        result.iterations = iteration
        result.actions_executed = total_actions
        result.message = f"Partie terminée: {self.current_game_state.value}"
        
        return result

    def _detect_game_state(
        self,
        solver_actions: List[Any],
        active: set[tuple[int, int]],
        frontier: set[tuple[int, int]],
    ) -> GameState:
        """
        Détection minimale : aucune condition de victoire automatique.
        On ne renvoie pas WON ici pour éviter d’arrêter la boucle prématurément.
        """
        try:
            # Si aucune action n’est disponible, on signale NO_ACTIONS pour stopper proprement la boucle.
            if not solver_actions and not active and not frontier:
                return GameState.NO_ACTIONS
            return GameState.PLAYING
        except Exception:
            return GameState.PLAYING

    def _should_continue(self, state: GameState, iterations: int) -> bool:
        if state in [GameState.WON, GameState.LOST, GameState.ERROR, GameState.NO_ACTIONS]:
            return False
        if iterations >= self.max_iterations:
            return False
        if self.stop_requested:
            return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        return self.stats.copy()

    def reset_stats(self):
        self.stats = {
            'games_played': 0,
            'games_won': 0,
            'games_lost': 0,
            'total_iterations': 0,
            'total_actions': 0,
            'total_time': 0.0,
            'errors': [],
            'total_safe_actions': 0,
            'total_flag_actions': 0,
            'actions_per_iteration': [],
            'analysis_time_per_iteration': [],
            'solver_time_per_iteration': [],
        }
        print("[INFO] Statistiques GameLoopService remises à zéro")
