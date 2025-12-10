#!/usr/bin/env python3
"""
Service de configuration de session - Navigation, initialisation et nettoyage
Gère toute la session de jeu : navigation, initialisation, configuration et nettoyage
"""

from typing import Dict, Any, Optional
from src.lib.s0_navigation.browser_manager import BrowserManager
from src.lib.s0_navigation.game_controller import GameSessionController, NavigationController
from src.lib.s0_navigation.coordinate_system import CoordinateConverter, GridViewportMapper
from src.lib.config import DIFFICULTY_CONFIG, DEFAULT_DIFFICULTY, GAME_CONFIG

class SessionSetupService:
    """Service de configuration complète de session de jeu"""
    
    def __init__(self, auto_close_browser: bool = False):
        """
        Initialise le service de session
        
        Args:
            auto_close_browser: True pour fermer automatiquement le navigateur, 
                               False pour demander à l'utilisateur (défaut)
        """
        self.browser_manager = None
        self.driver = None
        self.session_controller: Optional[GameSessionController] = None
        self.navigation_controller: Optional[NavigationController] = None
        self.coordinate_converter = None
        self.viewport_mapper = None
        self.is_initialized = False
        self.auto_close_browser = auto_close_browser
    
    def setup_session(self, difficulty: str = None) -> Dict[str, Any]:
        """
        Configure et démarre complètement une session de jeu
        
        Args:
            difficulty: Difficulté souhaitée (None = demande à l'utilisateur via GameController)
            
        Returns:
            Dict: Résultat complet de la configuration
        """
        try:
            print("[SESSION] Configuration de la session de jeu...")
            
            # 0. Initialiser la session (sans créer de partie encore)
            from src.lib.s0_navigation.game_session_manager import SessionState
            # Forcer une nouvelle instance pour éviter la persistance
            self.game_session = SessionState.create_new_session()
            
            # 1. Déterminer la difficulté AVANT de créer la partie
            if not difficulty:
                print("[SESSION] Aucune difficulté spécifiée, demande à l'utilisateur...")
                difficulty = GameSessionController.get_difficulty_from_user()
            
            print(f"[SESSION] Difficulté sélectionnée: {difficulty}")
            
            # 2. Créer la partie maintenant que la difficulté est connue
            state = self.game_session['state']
            storage = self.game_session['storage']
            
            # Nettoyer les anciennes parties
            storage.cleanup_old_games(3)
            
            # Créer la nouvelle partie
            game_id = state.spawn_new_game(difficulty)
            print(f"[GAME] Nouvelle partie initialisée: {game_id} (difficulté: {state.difficulty or 'non spécifiée'})")
            print(f"[GAME] Itération initiale: {state.iteration_num}")
            
            # Préparer le stockage
            storage.ensure_storage_ready(state, create_metadata=True)
            print(f"[SESSION] Partie initialisée avec ID: {game_id}")
            
            # 3. Récupérer l'URL depuis la configuration
            url = GAME_CONFIG['url']
            print(f"[SESSION] URL du jeu: {url}")
            
            # 3. Lancer Chrome
            if not self.is_initialized:
                print("[SESSION] Lancement du navigateur Chrome...")
                self.browser_manager = BrowserManager()
                
                if not self.browser_manager.start_browser():
                    return {
                        'success': False,
                        'error': 'browser_start_failed',
                        'message': 'Impossible de démarrer le navigateur'
                    }
                
                self.driver = self.browser_manager.get_driver()
                self.session_controller = GameSessionController(self.driver)
                self.navigation_controller = NavigationController(self.driver)
                self.coordinate_converter = CoordinateConverter(driver=self.driver)
                self.viewport_mapper = GridViewportMapper(self.coordinate_converter, self.driver)
                self.is_initialized = True
            
            # 4. Naviguer vers le site
            if url:
                print(f"[SESSION] Navigation vers {url}...")
                if not self.browser_manager.navigate_to(url):
                    return {
                        'success': False,
                        'error': 'navigation_failed',
                        'message': 'Impossible de naviguer vers le site'
                    }
            
            # 5. Configurer le jeu avec la difficulté déterminée
            print(f"[SESSION] Configuration du jeu en mode {difficulty}...")
            success = self.session_controller.select_game_mode(difficulty)
            
            if not success:
                return {
                    'success': False,
                    'error': 'game_setup_failed',
                    'message': 'Échec de la configuration du jeu'
                }
            
            # 6. Récupérer la configuration
            config = DIFFICULTY_CONFIG.get(difficulty, DIFFICULTY_CONFIG[DEFAULT_DIFFICULTY])

            if self.session_controller and self.session_controller.converter:
                self.coordinate_converter = self.session_controller.converter
                self.viewport_mapper = self.session_controller.viewport_mapper
            if self.navigation_controller:
                self.navigation_controller.converter = self.coordinate_converter
                self.navigation_controller.viewport_mapper = self.viewport_mapper
            
            print(f"[SUCCES] Session configurée avec succès!")
            print(f"   Mode: {config['name']}")
            print(f"   Difficulté: {difficulty}")
            
            return {
                'success': True,
                'difficulty': difficulty,
                'config': config,
                'driver': self.driver,
                'session_controller': self.session_controller,
                'navigation_controller': self.navigation_controller,
                'browser_manager': self.browser_manager,
                'message': f'Session configurée en mode {config["name"]}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Erreur lors de la configuration de la session: {e}'
            }
    
    def get_driver(self):
        """Récupère le driver Selenium après configuration"""
        if not self.is_initialized:
            raise RuntimeError("La session n'a pas été configurée. Appelez setup_session() d'abord.")
        return self.driver
    
    # def get_bot(self):
    #     """Compatibilité: renvoie le contrôleur de navigation."""
    #     if not self.is_initialized:
    #         raise RuntimeError("La session n'a pas été configurée. Appelez setup_session() d'abord.")
    #     return self.navigation_controller

    def get_navigation_controller(self):
        if not self.is_initialized:
            raise RuntimeError("La session n'a pas été configurée. Appelez setup_session() d'abord.")
        return self.navigation_controller

    def get_session_controller(self):
        if not self.is_initialized:
            raise RuntimeError("La session n'a pas été configurée. Appelez setup_session() d'abord.")
        return self.session_controller
    
    def get_coordinate_converter(self):
        """Récupère le convertisseur de coordonnées après configuration"""
        if not self.is_initialized:
            raise RuntimeError("La session n'a pas été configurée. Appelez setup_session() d'abord.")
        return self.coordinate_converter
    
    def get_viewport_mapper(self):
        """Récupère le mapper de viewport après configuration"""
        if not self.is_initialized:
            raise RuntimeError("La session n'a pas été configurée. Appelez setup_session() d'abord.")
        return self.viewport_mapper
    
    def get_browser_manager(self):
        """Récupère le gestionnaire de navigateur après configuration"""
        if not self.is_initialized:
            raise RuntimeError("La session n'a pas été configurée. Appelez setup_session() d'abord.")
        return self.browser_manager
    
    def get_anchor_element(self, driver=None):
        """Retourne l'élément anchor pour le système de coordonnées"""
        current_driver = driver or self.driver
        if not current_driver:
            raise RuntimeError("Aucun driver disponible. Session non configurée.")
        
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            anchor = WebDriverWait(current_driver, 10).until(
                EC.presence_of_element_located((By.ID, "anchor"))
            )
            return anchor
        except Exception as e:
            raise RuntimeError(f"Impossible de trouver l'élément anchor: {e}")
    
    def cleanup_session(self) -> bool:
        """Termine et nettoie la session de jeu"""
        try:
            print("[CLEANUP] Nettoyage de la session...")
            
            if not self.is_initialized:
                print("[CLEANUP] Aucune session active à nettoyer")
                return True
            
            # Si auto_close_browser=False, attendre que l'utilisateur appuie sur Entrée
            if self.browser_manager and not self.auto_close_browser:
                print("[INFO] Le navigateur est encore ouvert.")
                print("Appuyez sur Entrée pour fermer le navigateur et terminer la session...")
                input()  # Attendre que l'utilisateur appuie sur Entrée
            
            # Utiliser les méthodes des librairies pour le nettoyage
            if self.browser_manager:
                print("[FIN] Fermeture du navigateur...")
                self.browser_manager.stop_browser()
            
            self.driver = None
            self.bot = None
            self.browser_manager = None
            self.is_initialized = False
            
            print("[SUCCES] Session nettoyée avec succès")
            return True
            
        except Exception as e:
            print(f"[ERREUR] Erreur lors du nettoyage de la session: {e}")
            return False
    
    def get_game_id(self):
        """Récupère l'ID de partie actuel"""
        if not hasattr(self, 'game_session') or not self.game_session:
            return None
        return self.game_session['state'].game_id
    
    def get_game_session(self):
        """Récupère la session de jeu complète"""
        return self.game_session
    
    def is_session_active(self) -> bool:
        """Vérifie si la session est active"""
        return self.is_initialized and self.driver is not None
