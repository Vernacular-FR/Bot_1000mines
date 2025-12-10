"""
Service de boucle de jeu complète pour le démineur.
Orchestre le cycle analyse → résolution → exécution → répétition en utilisant les services existants.
"""

import time
import os
import sys
import shutil
import json
from typing import Dict, Any, Optional, List
from enum import Enum

# Imports du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.lib.s0_navigation.game_session_manager import SessionState
from src.lib.s0_navigation.coordinate_system import CoordinateConverter, GridViewportMapper
from src.lib.s3_tensor.cell import CellSymbol
from src.lib.s3_tensor.grid_state import GamePersistence

# Imports des services
from .s1_session_setup_service import SessionSetupService
from .s1_zone_capture_service import ZoneCaptureService
from .s2_optimized_analysis_service import OptimizedAnalysisService
from .s3_game_solver_service import GameSolverService
from .s4_action_executor_service import ActionExecutorService

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
    def __init__(self, session_service: SessionSetupService, 
                 max_iterations: int = 100, iteration_timeout: float = 60.0,
                 delay_between_iterations: float = 1.0, game_session=None):
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
        
        # Utiliser le gestionnaire centralisé de session fourni ou en créer un nouveau
        if game_session is None:
            self.game_session = SessionState.create_new_session()
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
        self.persistence = GamePersistence(
            base_path=self.game_base_path,
            metadata_path=self.game_paths.get('metadata'),
            actions_dir=self.game_paths.get('actions')
        )
        
        # Initialiser les services
        self.capture_service = ZoneCaptureService(
            driver=self.driver, 
            paths=self.game_paths, 
            game_id=self.game_id,
            session_service=session_service
        )
        self.analysis_service = OptimizedAnalysisService(paths=self.game_paths)
        self.solver_service = GameSolverService(paths=self.game_paths)
        self.action_service = ActionExecutorService(self.coordinate_converter, self.driver)
        if hasattr(self.analysis_service, "grid_db"):
            self.action_service.set_grid_db(self.analysis_service.grid_db)
        
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
        Exécute une seule passe complète : Capture -> Analyse -> Solver -> Actions
        Utilise le gestionnaire centralisé de session pour le numéro d'itération.
        
        Args:
            iteration_num: Numéro de l'itération (si None, utilise la session courante)
        
        Returns:
            Dict: Résultat de la passe avec succès, actions exécutées, état du jeu, etc.
        """
        # Utiliser le numéro d'itération de la session si non fourni
        if iteration_num is None:
            iteration_num = self.game_session['state'].iteration_num
        
        try:
            pass_result = {
                'success': False,
                'actions_executed': 0,
                'game_state': self.current_game_state.value,
                'message': '',
                'files_saved': []
            }
            
            # 1. Capture de la zone de jeu (s1_zone)
            print("[CAPTURE] Capture de la zone de jeu...")
            capture_result = self.capture_service.capture_game_zone_inside_interface(
                self.session_service, 
                iteration_num=iteration_num
            )
            
            if not capture_result['success']:
                pass_result['message'] = f"Erreur capture: {capture_result['message']}"
                return pass_result
            
            # 2. Analyse de la grille
            print("[ANALYSE] Analyse de la grille...")
            grid_zone = capture_result['grid_zone']
            zone_bounds = (grid_zone['start_x'], grid_zone['start_y'], grid_zone['end_x'], grid_zone['end_y'])
            
            analysis_result = self.analysis_service.analyze_from_path(capture_result['zone_path'], zone_bounds=zone_bounds)
            
            if not analysis_result['success']:
                pass_result['message'] = f"Erreur analyse: {analysis_result.get('message', 'Erreur inconnue')}"
                return pass_result
            
            # Utiliser directement le fichier de zone créé par le service de capture
            start_x, start_y, end_x, end_y = zone_bounds
            pass_result['files_saved'].append(capture_result['zone_path'])
            print(f"[SAVE] Zone déjà sauvegardée: {capture_result['zone_path']}")
            
            # Ajouter le fichier d'analyse créé
            if analysis_result.get('db_path'):
                pass_result['files_saved'].append(analysis_result['db_path'])
                print(f"[SAVE] Analyse sauvegardée: {analysis_result['db_path']}")
            
            # Ajouter l'overlay d'analyse si généré
            if analysis_result.get('overlay_path'):
                pass_result['files_saved'].append(analysis_result['overlay_path'])
                print(f"[SAVE] Overlay analyse sauvegardé: {analysis_result['overlay_path']}")
            
            # Vérification état fin de jeu (Mines / Victoire) via l'analyse
            detected_state = self._detect_game_state(analysis_result)
            if detected_state != GameState.PLAYING:
                self.current_game_state = detected_state
                pass_result['game_state'] = detected_state.value
                pass_result['message'] = f"Partie terminée: {detected_state.value}"
                pass_result['success'] = True  # La passe a réussi même si le jeu est fini
                return pass_result
            
            # 3. Résolution
            print("[SOLVEUR] Résolution du puzzle...")
            solve_result = self.solver_service.solve_from_db_path(
                analysis_result['db_path'], 
                capture_result['zone_path'],
                game_id=self.game_id,
                iteration_num=iteration_num
            )
            
            if not solve_result['success']:
                pass_result['message'] = f"Résolution partielle: {solve_result.get('message', 'Erreur inconnue')}"
                pass_result['success'] = True  # La passe a réussi même si résolution partielle
                return pass_result
            
            # L'overlay est déjà sauvegardé au bon endroit avec la bonne nomenclature
            if solve_result.get('overlay_path'):
                print(f"[SAVE] Overlay solver sauvegardé: {solve_result['overlay_path']}")
                pass_result['files_saved'].append(solve_result['overlay_path'])
            
            # 4. Exécution des actions
            solve_result['analysis_result'] = analysis_result
            game_actions = self.solver_service.convert_actions_to_game_actions(solve_result)
            
            if not game_actions:
                self.current_game_state = GameState.NO_ACTIONS
                pass_result['game_state'] = GameState.NO_ACTIONS.value
                pass_result['message'] = "Aucune action trouvée par le solveur"
                pass_result['success'] = True  # La passe a réussi
                return pass_result
            
            print(f"[EXÉCUTION] Exécution de {len(game_actions)} actions...")
            execution_result = self.action_service.execute_batch(game_actions)
            
            # Sauvegarder les actions dans s4_actions
            actions_save_path = self.persistence.save_actions(
                self.game_id,
                iteration_num,
                zone_bounds,
                game_actions,
                execution_result
            )
            pass_result['files_saved'].append(actions_save_path)
            print(f"[SAVE] Actions sauvegardées: {actions_save_path}")
            
            pass_result['success'] = True
            pass_result['actions_executed'] = execution_result['executed_count']
            pass_result['message'] = f"Passe réussie: {execution_result['executed_count']} actions exécutées"
            
            return pass_result

        except Exception as e:
            print(f"[ERREUR] Exception dans la passe: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'actions_executed': 0,
                'game_state': GameState.ERROR.value,
                'message': f"Erreur critique: {str(e)}",
                'files_saved': []
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
        
        # Fin de partie - Mettre à jour les métadonnées
        total_time = time.time() - start_time
        self.stats['total_time'] = total_time
        self.stats['iterations'] = iteration
        self.stats['total_actions'] = total_actions
        
        # Mettre à jour le fichier de métadonnées
        metadata = self.persistence.update_metadata({
            "end_time": time.time(),
            "end_datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": total_time,
            "iterations": iteration,
            "total_actions": total_actions,
            "final_state": self.current_game_state.value,
            "success": self.current_game_state == GameState.WON
        })
        print(f"[GAME] Métadonnées sauvegardées: {self.persistence.metadata_path}")
        
        result = GameResult()
        result.success = (self.current_game_state == GameState.WON)
        result.final_state = self.current_game_state
        result.total_time = total_time
        result.iterations = iteration
        result.actions_executed = total_actions
        result.message = f"Partie terminée: {self.current_game_state.value}"
        
        return result

    def _detect_game_state(self, analysis_result: Dict[str, Any]) -> GameState:
        """
        Détecte l'état actuel du jeu via l'analyse.
        """
        # 1. Vérifier la présence de mines (Défaite)
        db_path = analysis_result.get('db_path')
        if db_path and os.path.exists(db_path):
            from src.lib.s3_tensor.grid_state import GamePersistence, GridDB
            grid_db = GridDB(db_path)
            cells = grid_db.get_all_cells()
            
            for cell in cells:
                if cell['type'] == CellSymbol.MINE.value:
                    print("[GAME] Mine détectée ! Partie perdue.")
                    return GameState.LOST

        # 2. Vérifier la victoire
        game_status = analysis_result.get('game_status', {})
        summary = analysis_result.get('summary', {})
        symbol_distribution = game_status.get('symbol_distribution', summary.get('symbol_distribution', {}))
        
        unknown_count = symbol_distribution.get(CellSymbol.UNKNOWN.value, 0)
        unrevealed_count = symbol_distribution.get(CellSymbol.UNREVEALED.value, 0)
        flag_count = symbol_distribution.get(CellSymbol.FLAG.value, 0)
        
        total_cells = summary.get('total_cells', 0)
        
        # Si on a tout révélé sauf les mines (supposées)
        if total_cells > 0 and unknown_count == 0 and unrevealed_count == 0: # Cas simple
             print("[GAME] Plus de cases inconnues ! Partie gagnée.")
             return GameState.WON
        
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
            'errors': []
        }
        print("[INFO] Statistiques GameLoopService remises à zéro")
