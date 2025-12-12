"""
Service d'exécution d'actions pour le jeu de démineur.
Responsable de l'exécution des actions du solveur (clics, drapeaux) sur l'interface utilisateur.
"""

import time
import sys
import os
from typing import List, Tuple, Optional, Dict, Any

from enum import Enum

# Imports du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.lib.s0_navigation.coordinate_system import CoordinateConverter, GridViewportMapper
from src.lib.s3_tensor.grid_state import GridDB

# Import du système de logging centralisé
from Logs.logger import save_bot_log


class ActionType(Enum):
    """Types d'actions possibles"""
    CLICK_LEFT = "click_left"      # Clic gauche (révéler cellule)
    CLICK_RIGHT = "click_right"    # Clic droit (poser/retirer drapeau)
    DOUBLE_CLICK = "double_click"  # Double-clic (si nécessaire)


class GameAction:
    """Représente une action à exécuter sur le jeu"""

    def __init__(self, action_type: ActionType, grid_x: int, grid_y: int,
                 confidence: float = 1.0, description: str = ""):
        """
        Initialise une action de jeu.

        Args:
            action_type: Type d'action (clic gauche, clic droit, etc.)
            grid_x: Coordonnée X dans la grille
            grid_y: Coordonnée Y dans la grille
            confidence: Niveau de confiance du solveur (0.0 à 1.0)
            description: Description textuelle de l'action
        """
        self.action_type = action_type
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.confidence = confidence
        self.description = description
        self.timestamp = time.time()

    def __repr__(self):
        return f"GameAction({self.action_type.value}, ({self.grid_x}, {self.grid_y}), conf={self.confidence:.2f})"
    
    def to_dict(self):
        """Convertit l'action en dictionnaire pour sérialisation"""
        return {
            'action_type': self.action_type.value,
            'grid_x': self.grid_x,
            'grid_y': self.grid_y,
            'confidence': self.confidence,
            'description': self.description,
            'timestamp': self.timestamp
        }


class ActionExecutorService:
    """
    Service responsable de l'exécution des actions du solveur sur l'interface de jeu.
    Gère les conversions de coordonnées et l'interaction avec le navigateur.
    """

    def __init__(self, coordinate_converter: CoordinateConverter, driver=None,
                 click_delay: float = 0.1, action_delay: float = 0.05,
                 grid_db: Optional[GridDB] = None):
        """
        Initialise le service d'exécution d'actions.

        Args:
            coordinate_converter: Convertisseur de coordonnées pour les conversions
            driver: Instance du WebDriver pour les interactions navigateur
            click_delay: Délai entre les clics (secondes)
            action_delay: Délai entre les actions consécutives (secondes)
            grid_db: Instance GridDB pour persister les flags posés (optionnel)
        """
        self.coordinate_converter = coordinate_converter
        self.driver = driver
        self.click_delay = click_delay
        self.action_delay = action_delay
        self.grid_db = grid_db

        # Import et initialisation du GameController
        from src.lib.s0_navigation.game_controller import NavigationController
        self.game_controller = NavigationController(driver, coordinate_converter, None)

        # Statistiques d'exécution
        self.stats = {
            'actions_executed': 0,
            'clicks_left': 0,
            'clicks_right': 0,
            'errors': 0,
            'total_execution_time': 0.0
        }

        print("[INFO] ActionExecutorService initialisé")
        save_bot_log({"service": "ActionExecutorService", "status": "initialized"},
                    "Service initialisé", "action_executor_init")

    def set_driver(self, driver):
        """Définit l'instance du WebDriver"""
        self.driver = driver
        print("[INFO] WebDriver défini dans ActionExecutorService")

    def set_grid_db(self, grid_db: GridDB):
        """Définit la GridDB utilisée pour refléter les flags posés"""
        self.grid_db = grid_db
        print("[INFO] GridDB connectée à ActionExecutorService")

    def execute_batch(self, actions: List[GameAction]) -> Dict[str, Any]:
        """
        Exécute un lot d'actions sur l'interface de jeu.
        Alias pour execute_actions pour compatibilité.

        Args:
            actions: Liste des actions à exécuter

        Returns:
            Dict avec le résultat de l'exécution
        """
        return self.execute_actions(actions)

    def execute_actions(self, actions: List[GameAction]) -> Dict[str, Any]:
        """
        Exécute une liste d'actions sur l'interface de jeu.

        Args:
            actions: Liste des actions à exécuter

        Returns:
            Dict avec le résultat de l'exécution
        """
        if not self.driver:
            error_msg = "WebDriver non défini - impossible d'exécuter les actions"
            print(f"[ERREUR] {error_msg}")
            return {
                'success': False,
                'message': error_msg,
                'executed_count': 0,
                'errors': len(actions)
            }

        executed_count = 0
        errors = 0
        start_time = time.time()

        print(f"[ACTION] Exécution de {len(actions)} actions...")

        for i, action in enumerate(actions):
            try:
                success = self._execute_single_action(action)

                if success:
                    executed_count += 1
                    self.stats['actions_executed'] += 1
                    if action.action_type == ActionType.CLICK_LEFT:
                        self.stats['clicks_left'] += 1
                    elif action.action_type == ActionType.CLICK_RIGHT:
                        self.stats['clicks_right'] += 1
                else:
                    errors += 1
                    self.stats['errors'] += 1

                # Délai entre les actions
                if i < len(actions) - 1:  # Pas de délai après la dernière action
                    time.sleep(self.action_delay)

            except Exception as e:
                print(f"[ERREUR] Échec exécution action {action}: {e}")
                errors += 1
                self.stats['errors'] += 1

        execution_time = time.time() - start_time
        self.stats['total_execution_time'] += execution_time

        result = {
            'success': errors == 0,
            'executed_count': executed_count,
            'errors': errors,
            'execution_time': execution_time,
            'actions_per_second': executed_count / execution_time if execution_time > 0 else 0
        }

        print(f"[ACTION] Exécution terminée: {executed_count}/{len(actions)} actions réussies en {execution_time:.2f}s")

        # Log des statistiques
        save_bot_log({
            "actions_total": len(actions),
            "actions_executed": executed_count,
            "errors": errors,
            "execution_time": execution_time
        }, f"Actions exécutées: {executed_count}/{len(actions)}", "action_execution")

        return result

    def _execute_single_action(self, action: GameAction) -> bool:
        """
        Exécute une seule action.

        Args:
            action: Action à exécuter

        Returns:
            True si succès, False sinon
        """
        try:
            success = self.game_controller.execute_game_action(action, coord_system=self.coordinate_converter)
            if success:
                print(f"[ACTION] {action.action_type.value} exécutée sur ({action.grid_x}, {action.grid_y})")
                if action.action_type == ActionType.CLICK_RIGHT:
                    self._mark_flag_in_db(action)
            return success

        except Exception as e:
            print(f"[ERREUR] Échec exécution action {action}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques d'exécution.

        Returns:
            Dict avec les statistiques
        """
        return self.stats.copy()

    def reset_stats(self):
        """Remet à zéro les statistiques"""
        self.stats = {
            'actions_executed': 0,
            'clicks_left': 0,
            'clicks_right': 0,
            'errors': 0,
            'total_execution_time': 0.0
        }
        print("[INFO] Statistiques ActionExecutorService remises à zéro")

    def _mark_flag_in_db(self, action: GameAction):
        """Persiste immédiatement un drapeau dans GridDB pour les overlays incrémentaux"""
        if not self.grid_db:
            return
        try:
            self.grid_db.add_cell(
                action.grid_x,
                action.grid_y,
                {
                    "type": "flag",
                    "confidence": action.confidence,
                    "state": "PROCESSED",
                },
            )
            self.grid_db.flush_to_disk()
        except Exception as e:
            print(f"[WARN] Impossible de persister le flag ({action.grid_x}, {action.grid_y}) : {e}")
