"""
Service de Navigation - Mouvements simples de la vue

Version mise à jour pour utiliser directement la pile S0 (BrowserNavigation,
CoordinateConverter, InterfaceDetector).
"""

import time
from typing import Optional, Any

from lib.s0_navigation import BrowserNavigation, CoordinateConverter, InterfaceDetector


class NavigationService:
    """Service pour les mouvements simples de navigation dans le jeu."""
    
    def __init__(self, driver, session_service=None):
        """
        Initialise le service de navigation.
        
        Args:
            driver: Instance WebDriver pour interagir avec le jeu
            session_service: Instance SessionSetupService déjà configurée (optionnel)
        """
        self.driver = driver
        self.session_service = session_service
        
        self.browser_navigation: Optional[BrowserNavigation] = None
        self.coordinate_converter: Optional[CoordinateConverter] = None
        self.interface_detector: Optional[InterfaceDetector] = None
        self.legacy_bot: Optional[Any] = None
        self.legacy_coordinate_system: Optional[Any] = None
        
        if session_service:
            self._setup_from_session()
        else:
            self._bootstrap_from_driver()
    
    def _bootstrap_from_driver(self):
        """Initialise les composants S0 directement depuis le driver."""
        self.browser_navigation = BrowserNavigation(self.driver)
        self.coordinate_converter = CoordinateConverter()
        self.interface_detector = InterfaceDetector()
    
    def _setup_from_session(self):
        """Récupère les composants S0 fournis par SessionSetupService (nouvelle pile)."""
        try:
            if hasattr(self.session_service, "get_browser_navigation"):
                self.browser_navigation = self.session_service.get_browser_navigation()
            if hasattr(self.session_service, "get_coordinate_converter"):
                self.coordinate_converter = self.session_service.get_coordinate_converter()
            if hasattr(self.session_service, "get_interface_detector"):
                self.interface_detector = self.session_service.get_interface_detector()
            if hasattr(self.session_service, "get_legacy_bot"):
                self.legacy_bot = self.session_service.get_legacy_bot()
            if hasattr(self.session_service, "get_coordinate_system"):
                self.legacy_coordinate_system = self.session_service.get_coordinate_system()
        except Exception as err:
            print(f"[NAVIGATION] Impossible de récupérer les composants S0: {err}")
            self._bootstrap_from_driver()
        
        if not self.browser_navigation:
            self.browser_navigation = BrowserNavigation(self.driver)
        if not self.coordinate_converter:
            self.coordinate_converter = CoordinateConverter()
        if not self.interface_detector:
            self.interface_detector = InterfaceDetector()
    
    def move_viewport(self, dx, dy, wait_after=1.0, log=True):
        """
        Déplace la vue du nombre de pixels spécifié en utilisant BrowserNavigation.scroll_to.
        
        Args:
            dx: Déplacement horizontal (pixels, positif = droite)
            dy: Déplacement vertical (pixels, positif = bas)
            wait_after: Temps d'attente après mouvement
            log: Active les logs
            
        Returns:
            dict: Résultat du mouvement
        """
        if self.legacy_bot and hasattr(self.legacy_bot, "move_view_js"):
            try:
                success = self.legacy_bot.move_view_js(dx, dy)
                if wait_after > 0:
                    time.sleep(wait_after)
                if log:
                    direction = f"dx={dx}, dy={dy}"
                    print(f"[NAVIGATION] Legacy move_view_js ({direction}) -> {'OK' if success else 'ÉCHEC'}")
                return {
                    "success": success,
                    "dx": dx,
                    "dy": dy,
                    "message": "Viewport déplacé (legacy bot)" if success else "Échec déplacement legacy",
                }
            except Exception as err:
                if log:
                    print(f"[NAVIGATION] Legacy move_view_js error: {err}")
                # fallback to BrowserNavigation
        
        if not self.browser_navigation:
            return {
                "success": False,
                "message": "BrowserNavigation non disponible",
                "dx": dx,
                "dy": dy,
            }
        
        try:
            success = self.browser_navigation.scroll_to(dx, dy)
            if wait_after > 0:
                time.sleep(wait_after)
            if log:
                direction = f"dx={dx}, dy={dy}"
                print(f"[NAVIGATION] Déplacement viewport ({direction}) -> {'OK' if success else 'ÉCHEC'}")
            return {
                "success": success,
                "dx": dx,
                "dy": dy,
                "message": "Viewport déplacé" if success else "Échec du déplacement",
            }
        except Exception as exc:
            if log:
                print(f"[NAVIGATION] Erreur lors du déplacement: {exc}")
            return {
                "success": False,
                "dx": dx,
                "dy": dy,
                "message": str(exc),
            }

    def prepare_for_capture(self, wait_after: float = 0.0) -> bool:
        """
        Rafraîchit les références nécessaires avant une capture (anchor legacy, etc.).
        """
        try:
            if self.legacy_coordinate_system and hasattr(self.legacy_coordinate_system, "setup_anchor"):
                self.legacy_coordinate_system.setup_anchor()
                if wait_after > 0:
                    time.sleep(wait_after)
                return True
        except Exception as err:
            print(f"[NAVIGATION] prepare_for_capture legacy error: {err}")
        return False

