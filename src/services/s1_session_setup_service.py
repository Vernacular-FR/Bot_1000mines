#!/usr/bin/env python3
"""
Service de configuration de session – version minimale alignée sur le pipeline s0→s2.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.config import DIFFICULTY_CONFIG, GAME_CONFIG, DEFAULT_DIFFICULTY
from src.lib.s0_interface.controller import InterfaceController
from src.lib.s0_interface.s00_browser_manager import BrowserManager
from src.lib.s0_interface.s03_game_controller import GameSessionController
from src.lib.s0_interface.s01_game_session_manager import SessionState, SessionStorage
from src.lib.s3_storage.s30_session_context import set_session_context


class SessionSetupService:
    """
    Façade métier pour gérer l’ouverture du navigateur, la navigation vers 1000mines
    et l’initialisation d’un InterfaceController prêt à l’emploi.
    """

    def __init__(self, auto_close_browser: bool = False):
        self.browser_manager = BrowserManager()
        self.interface_controller: Optional[InterfaceController] = None
        self.session_controller: Optional[GameSessionController] = None
        self.auto_close_browser = auto_close_browser
        self.is_initialized = False
        self.session_state = SessionState()
        self.session_storage = SessionStorage()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def setup_session(self, difficulty: Optional[str] = None) -> Dict[str, Any]:
        try:
            if not self.browser_manager.start_browser():
                return {
                    "success": False,
                    "error": "browser_start_failed",
                    "message": "Impossible de démarrer le navigateur",
                }

            driver = self.browser_manager.get_driver()
            if driver is None:
                return {
                    "success": False,
                    "error": "driver_unavailable",
                    "message": "Driver Selenium indisponible",
                }

            target_url = GAME_CONFIG.get("url")
            if target_url and not self.browser_manager.navigate_to(target_url):
                return {
                    "success": False,
                    "error": "navigation_failed",
                    "message": f"Impossible de naviguer vers {target_url}",
                }

            self.session_controller = GameSessionController(driver)
            chosen_difficulty = difficulty or self.session_controller.get_difficulty_from_user()

            # Créer une nouvelle session de jeu avec ID unique
            game_id = self.session_state.spawn_new_game(chosen_difficulty)
            storage_info = self.session_storage.ensure_storage_ready(self.session_state)
            # Initialiser le contexte global (export_root défini plus tard par GameLoop)
            set_session_context(
                game_id=game_id,
                iteration=self.session_state.iteration_num,
                export_root="",
                overlay_enabled=False,
            )

            print(f"[SESSION] Configuration du jeu en mode {chosen_difficulty}…")
            print(f"[SESSION] Game ID: {game_id}")
            if not self.session_controller.select_game_mode(chosen_difficulty):
                return {
                    "success": False,
                    "error": "game_setup_failed",
                    "message": "Échec de la sélection de la difficulté",
                }

            self.interface_controller = InterfaceController.from_browser(self.browser_manager)
            self.is_initialized = True

            config = DIFFICULTY_CONFIG.get(chosen_difficulty, DIFFICULTY_CONFIG[DEFAULT_DIFFICULTY])
            return {
                "success": True,
                "difficulty": chosen_difficulty,
                "config": config,
                "interface": self.interface_controller,
                "game_id": game_id,
                "paths": storage_info["paths"],
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "message": f"Erreur lors de la configuration de la session: {exc}",
            }

    def cleanup_session(self) -> bool:
        try:
            if self.browser_manager and not self.auto_close_browser:
                try:
                    input("[SESSION] Partie terminée. Appuyez sur Entrée pour fermer le navigateur…")
                except Exception:
                    pass

            if self.browser_manager:
                self.browser_manager.stop_browser()

            self.interface_controller = None
            self.session_controller = None
            self.is_initialized = False
            return True
        except Exception as exc:
            print(f"[CLEANUP] Erreur: {exc}")
            return False

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_interface(self) -> InterfaceController:
        if not self.is_initialized or not self.interface_controller:
            raise RuntimeError("Session non initialisée. Appelez setup_session() d'abord.")
        return self.interface_controller

    def get_driver(self):
        if not self.is_initialized:
            raise RuntimeError("Session non initialisée. Appelez setup_session() d'abord.")
        return self.browser_manager.get_driver()

    def get_coordinate_converter(self):
        if not self.is_initialized or not self.interface_controller:
            raise RuntimeError("Session non initialisée. Appelez setup_session() d'abord.")
        return self.interface_controller.converter

    def get_viewport_mapper(self):
        if not self.is_initialized or not self.interface_controller:
            raise RuntimeError("Session non initialisée. Appelez setup_session() d'abord.")
        return self.interface_controller.navigator.viewport_mapper

    def get_browser_manager(self) -> BrowserManager:
        if not self.is_initialized:
            raise RuntimeError("Session non initialisée. Appelez setup_session() d'abord.")
        return self.browser_manager

    def is_session_active(self) -> bool:
        return self.is_initialized
