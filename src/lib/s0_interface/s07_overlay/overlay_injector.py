"""
Module d'injection et de gestion de l'overlay UI dans le navigateur.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from selenium.webdriver.remote.webdriver import WebDriver

from .types import OverlayType, OverlayData, OverlayConfig


class OverlayInjector:
    """
    Injecte et gère l'overlay UI JavaScript dans la page 1000mines.com.
    """
    
    def __init__(self, config: Optional[OverlayConfig] = None):
        self.config = config or OverlayConfig()
        self._template_js: Optional[str] = None
        self._is_injected = False
    
    def _load_template(self) -> str:
        """Charge le template JavaScript de l'overlay."""
        if self._template_js is None:
            template_path = Path(__file__).parent / "overlay_template.js"
            self._template_js = template_path.read_text(encoding='utf-8')
        return self._template_js
    
    def inject(self, driver: WebDriver) -> bool:
        """
        Injecte l'overlay UI dans la page.
        
        Args:
            driver: Instance Selenium WebDriver
            
        Returns:
            True si injection réussie, False sinon
        """
        try:
            # Charger le template
            js_code = self._load_template()
            
            # Injecter dans la page
            driver.execute_script(js_code)
            
            # Initialiser l'overlay
            result = driver.execute_script("""
                if (window.BotOverlay) {
                    return window.BotOverlay.init();
                }
                return false;
            """)
            
            if result:
                self._is_injected = True
                print("[OVERLAY] UI injectée avec succès")
                
                # Définir l'overlay par défaut
                if self.config.default_overlay != OverlayType.OFF:
                    self.set_overlay(driver, self.config.default_overlay)
            else:
                print("[OVERLAY] Échec de l'initialisation")
                self._is_injected = False
            
            return self._is_injected
            
        except Exception as e:
            print(f"[OVERLAY] Erreur lors de l'injection: {e}")
            self._is_injected = False
            return False
    
    def is_injected(self, driver: WebDriver) -> bool:
        """
        Vérifie si l'overlay est injecté dans la page.
        
        Args:
            driver: Instance Selenium WebDriver
            
        Returns:
            True si l'overlay est présent, False sinon
        """
        try:
            result = driver.execute_script("""
                return typeof window.BotOverlay !== 'undefined';
            """)
            return bool(result)
        except Exception:
            return False
    
    def set_overlay(self, driver: WebDriver, overlay_type: OverlayType) -> bool:
        """
        Change l'overlay actif.
        
        Args:
            driver: Instance Selenium WebDriver
            overlay_type: Type d'overlay à afficher
            
        Returns:
            True si changement réussi, False sinon
        """
        if not self._is_injected and not self.is_injected(driver):
            print("[OVERLAY] Overlay non injecté, injection automatique...")
            if not self.inject(driver):
                return False
        
        try:
            driver.execute_script(f"""
                if (window.BotOverlay) {{
                    window.BotOverlay.setOverlay('{overlay_type.value}');
                }}
            """)
            return True
        except Exception as e:
            print(f"[OVERLAY] Erreur lors du changement d'overlay: {e}")
            return False
    
    def update_data(
        self, 
        driver: WebDriver, 
        overlay_data: OverlayData
    ) -> bool:
        """
        Met à jour les données de l'overlay.
        
        Args:
            driver: Instance Selenium WebDriver
            overlay_data: Données à afficher
            
        Returns:
            True si mise à jour réussie, False sinon
        """
        if not self._is_injected and not self.is_injected(driver):
            print("[OVERLAY] Overlay non injecté, impossible de mettre à jour les données")
            return False
        
        try:
            # Convertir les données en JSON
            data_dict = overlay_data.to_dict()
            data_json = json.dumps(data_dict)
            
            # Appeler la fonction JS de mise à jour
            driver.execute_script(f"""
                if (window.BotOverlay) {{
                    window.BotOverlay.updateData('{overlay_data.overlay_type.value}', {data_json});
                }}
            """)
            
            return True
            
        except Exception as e:
            print(f"[OVERLAY] Erreur lors de la mise à jour des données: {e}")
            return False
    
    def render(self, driver: WebDriver) -> bool:
        """
        Force le rafraîchissement de l'overlay.
        
        Args:
            driver: Instance Selenium WebDriver
            
        Returns:
            True si rafraîchissement réussi, False sinon
        """
        if not self._is_injected and not self.is_injected(driver):
            return False
        
        try:
            driver.execute_script("""
                if (window.BotOverlay) {
                    window.BotOverlay.render();
                }
            """)
            return True
        except Exception as e:
            print(f"[OVERLAY] Erreur lors du rafraîchissement: {e}")
            return False
    
    def get_state(self, driver: WebDriver) -> Optional[Dict[str, Any]]:
        """
        Récupère l'état actuel de l'overlay.
        
        Args:
            driver: Instance Selenium WebDriver
            
        Returns:
            Dictionnaire avec l'état, ou None si erreur
        """
        if not self._is_injected and not self.is_injected(driver):
            return None
        
        try:
            state = driver.execute_script("""
                if (window.BotOverlay) {
                    return window.BotOverlay.getState();
                }
                return null;
            """)
            return state
        except Exception as e:
            print(f"[OVERLAY] Erreur lors de la récupération de l'état: {e}")
            return None
    
    def destroy(self, driver: WebDriver) -> bool:
        """
        Détruit l'overlay UI.
        
        Args:
            driver: Instance Selenium WebDriver
            
        Returns:
            True si destruction réussie, False sinon
        """
        if not self._is_injected and not self.is_injected(driver):
            return True  # Déjà détruit
        
        try:
            driver.execute_script("""
                if (window.BotOverlay) {
                    window.BotOverlay.destroy();
                    delete window.BotOverlay;
                }
            """)
            self._is_injected = False
            print("[OVERLAY] UI détruite")
            return True
            
        except Exception as e:
            print(f"[OVERLAY] Erreur lors de la destruction: {e}")
            return False


# Fonction helper pour créer une instance
def create_overlay_injector(
    enabled: bool = True,
    default_overlay: OverlayType = OverlayType.OFF
) -> OverlayInjector:
    """
    Crée une instance d'OverlayInjector avec configuration.
    
    Args:
        enabled: Active/désactive l'overlay
        default_overlay: Overlay affiché par défaut
        
    Returns:
        Instance configurée d'OverlayInjector
    """
    config = OverlayConfig(
        enabled=enabled,
        default_overlay=default_overlay
    )
    return OverlayInjector(config)
