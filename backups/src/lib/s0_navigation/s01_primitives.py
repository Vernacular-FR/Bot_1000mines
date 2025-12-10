"""
NavigationPrimitives - Interface d'interaction navigateur (S0.1)

Implémente les primitives d'interaction avec le jeu:
- Clic simple sur les cellules (révélation)
- Flag/déflag des mines
- Double-clic pour révélation rapide
- Scroll/pan du viewport
- Interface avec Selenium WebDriver
"""

import time
from typing import List, Tuple, Optional, Dict, Any, Protocol
from dataclasses import dataclass
from enum import Enum
import threading
from abc import ABC, abstractmethod

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import WebDriverException, TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class ActionResult(Enum):
    """Résultats des actions de navigation"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INVALID_COORDINATES = "invalid_coordinates"
    ELEMENT_NOT_FOUND = "element_not_found"
    DRIVER_ERROR = "driver_error"


@dataclass
class NavigationStats:
    """Statistiques des opérations de navigation"""
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    timeout_actions: int = 0
    average_action_time: float = 0.0
    click_accuracy: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Taux de succès"""
        if self.total_actions == 0:
            return 0.0
        return self.successful_actions / self.total_actions


class NavigationPrimitives(Protocol):
    """Interface pour les primitives de navigation S0"""
    
    def click_cell(self, x: int, y: int) -> bool:
        """Clic simple sur une cellule"""
        ...
    
    def flag_cell(self, x: int, y: int) -> bool:
        """Flag une cellule"""
        ...
    
    def double_click_cell(self, x: int, y: int) -> bool:
        """Double-clic sur une cellule (révélation rapide)"""
        ...
    
    def scroll_to(self, dx: int, dy: int) -> bool:
        """Scroll de la vue"""
        ...
    
    def get_current_viewport(self) -> Tuple[int, int, int, int]:
        """Retourne le viewport actuel (x, y, width, height)"""
        ...


class BrowserNavigation:
    """
    Implémentation des primitives de navigation via Selenium
    
    Fonctionnalités:
    - Interaction directe avec le navigateur
    - Gestion des erreurs et timeouts
    - Optimisation des séquences d'actions
    - Support pour les différents navigateurs
    """
    
    def __init__(self, driver: Optional['webdriver.Chrome'] = None,
                 action_timeout: float = 5.0,
                 click_delay: float = 0.1,
                 enable_action_chaining: bool = True):
        """
        Initialise la navigation navigateur
        
        Args:
            driver: Instance WebDriver (None = mode stub)
            action_timeout: Timeout pour chaque action
            click_delay: Délai entre les clics
            enable_action_chaining: Activer le chaînage d'actions
        """
        # Configuration
        self.action_timeout = action_timeout
        self.click_delay = click_delay
        self.enable_action_chaining = enable_action_chaining
        
        # WebDriver
        self.driver = driver
        self.action_chains: Optional[ActionChains] = None
        
        # État et coordination
        self._lock = threading.RLock()
        self._last_action_time: float = 0.0
        self._current_viewport: Tuple[int, int, int, int] = (0, 0, 800, 600)
        
        # Statistiques
        self._stats = NavigationStats()
        self._action_times: List[float] = []
        
        # Initialiser les chaînes d'actions si disponible
        if self.driver and self.enable_action_chaining and SELENIUM_AVAILABLE:
            self.action_chains = ActionChains(self.driver)
    
    def click_cell(self, x: int, y: int) -> bool:
        """
        Effectue un clic simple sur une cellule
        
        Args:
            x, y: Coordonnées grille de la cellule
            
        Returns:
            True si le clic a réussi
        """
        return self._execute_action('click', x, y, self._perform_click)
    
    def flag_cell(self, x: int, y: int) -> bool:
        """
        Effectue un clic droit pour flagger une cellule
        
        Args:
            x, y: Coordonnées grille de la cellule
            
        Returns:
            True si le flag a réussi
        """
        return self._execute_action('flag', x, y, self._perform_flag)
    
    def double_click_cell(self, x: int, y: int) -> bool:
        """
        Effectue un double-clic pour révélation rapide
        
        Args:
            x, y: Coordonnées grille de la cellule
            
        Returns:
            True si le double-clic a réussi
        """
        return self._execute_action('double_click', x, y, self._perform_double_click)
    
    def scroll_to(self, dx: int, dy: int) -> bool:
        """
        Effectue un scroll/pan de la vue
        
        Args:
            dx, dy: Déplacement en pixels
            
        Returns:
            True si le scroll a réussi
        """
        return self._execute_action('scroll', dx, dy, self._perform_scroll)
    
    def get_current_viewport(self) -> Tuple[int, int, int, int]:
        """
        Retourne le viewport actuel
        
        Returns:
            (x, y, width, height) du viewport
        """
        with self._lock:
            if self.driver and SELENIUM_AVAILABLE:
                try:
                    # Obtenir les dimensions du viewport via JavaScript
                    viewport_info = self.driver.execute_script("""
                        var canvas = document.querySelector('#gameCanvas');
                        if (canvas) {
                            var rect = canvas.getBoundingClientRect();
                            return {
                                x: rect.left,
                                y: rect.top,
                                width: rect.width,
                                height: rect.height
                            };
                        }
                        return {x: 0, y: 0, width: 800, height: 600};
                    """)
                    
                    self._current_viewport = (
                        viewport_info['x'],
                        viewport_info['y'],
                        viewport_info['width'],
                        viewport_info['height']
                    )
                except Exception:
                    # En cas d'erreur, utiliser les valeurs par défaut
                    pass
            
            return self._current_viewport
    
    def set_driver(self, driver: 'webdriver.Chrome') -> None:
        """
        Définit le WebDriver
        
        Args:
            driver: Instance WebDriver à utiliser
        """
        with self._lock:
            self.driver = driver
            if self.enable_action_chaining and SELENIUM_AVAILABLE:
                self.action_chains = ActionChains(driver)
    
    def _execute_action(self, action_type: str, x: int, y: int,
                        action_func) -> bool:
        """
        Exécute une action avec gestion d'erreur et statistiques
        
        Args:
            action_type: Type d'action
            x, y: Coordonnées
            action_func: Fonction d'action à exécuter
            
        Returns:
            True si succès
        """
        start_time = time.time()
        
        with self._lock:
            self._stats.total_actions += 1
            
            try:
                # Vérifier le driver
                if not self.driver or not SELENIUM_AVAILABLE:
                    self._stats.failed_actions += 1
                    return False
                
                # Respecter le délai entre les actions
                self._respect_action_delay()
                
                # Exécuter l'action
                result = action_func(x, y)
                
                # Mettre à jour les statistiques
                if result:
                    self._stats.successful_actions += 1
                else:
                    self._stats.failed_actions += 1
                
                # Enregistrer le temps d'action
                action_time = time.time() - start_time
                self._record_action_time(action_time)
                
                self._last_action_time = time.time()
                return result
                
            except TimeoutException:
                self._stats.timeout_actions += 1
                return False
                
            except WebDriverException:
                self._stats.failed_actions += 1
                return False
                
            except Exception:
                self._stats.failed_actions += 1
                return False
    
    def _perform_click(self, x: int, y: int) -> bool:
        """Effectue le clic simple"""
        try:
            # Convertir les coordonnées grille en coordonnées écran
            screen_x, screen_y = self._grid_to_screen(x, y)
            
            # Utiliser JavaScript pour un clic plus précis
            self.driver.execute_script(f"""
                var element = document.elementFromPoint({screen_x}, {screen_y});
                if (element) {{
                    element.click();
                    return true;
                }}
                return false;
            """)
            
            return True
            
        except Exception:
            # Fallback avec ActionChains
            if self.action_chains:
                screen_x, screen_y = self._grid_to_screen(x, y)
                self.action_chains.move_by_offset(screen_x, screen_y).click().perform()
                self.action_chains.reset_actions()
                return True
            return False
    
    def _perform_flag(self, x: int, y: int) -> bool:
        """Effectue le clic droit pour flag"""
        try:
            screen_x, screen_y = self._grid_to_screen(x, y)
            
            # Clic droit via JavaScript
            self.driver.execute_script(f"""
                var element = document.elementFromPoint({screen_x}, {screen_y});
                if (element) {{
                    var event = new MouseEvent('contextmenu', {{
                        bubbles: true,
                        cancelable: true,
                        clientX: {screen_x},
                        clientY: {screen_y}
                    }});
                    element.dispatchEvent(event);
                    return true;
                }}
                return false;
            """)
            
            return True
            
        except Exception:
            # Fallback avec ActionChains
            if self.action_chains:
                screen_x, screen_y = self._grid_to_screen(x, y)
                self.action_chains.move_by_offset(screen_x, screen_y).context_click().perform()
                self.action_chains.reset_actions()
                return True
            return False
    
    def _perform_double_click(self, x: int, y: int) -> bool:
        """Effectue le double-clic"""
        try:
            screen_x, screen_y = self._grid_to_screen(x, y)
            
            # Double-clic via JavaScript
            self.driver.execute_script(f"""
                var element = document.elementFromPoint({screen_x}, {screen_y});
                if (element) {{
                    element.dispatchEvent(new MouseEvent('dblclick', {{
                        bubbles: true,
                        cancelable: true,
                        clientX: {screen_x},
                        clientY: {screen_y}
                    }}));
                    return true;
                }}
                return false;
            """)
            
            return True
            
        except Exception:
            # Fallback avec ActionChains
            if self.action_chains:
                screen_x, screen_y = self._grid_to_screen(x, y)
                self.action_chains.move_by_offset(screen_x, screen_y).double_click().perform()
                self.action_chains.reset_actions()
                return True
            return False
    
    def _perform_scroll(self, dx: int, dy: int) -> bool:
        """Effectue le scroll/pan"""
        try:
            # Scroller via JavaScript
            self.driver.execute_script(f"""
                window.scrollBy({dx}, {dy});
                return true;
            """)
            
            return True
            
        except Exception:
            return False
    
    def _grid_to_screen(self, grid_x: int, grid_y: int) -> Tuple[int, int]:
        """
        Convertit les coordonnées grille en coordonnées écran
        
        Args:
            grid_x, grid_y: Coordonnées grille
            
        Returns:
            Coordonnées écran
        """
        # Cette conversion devrait être déléguée au CoordinateConverter
        # Pour l'instant, utilisation d'une conversion simple
        cell_size = 24  # Taille par défaut
        
        # Obtenir la position du canvas
        viewport_x, viewport_y, _, _ = self.get_current_viewport()
        
        screen_x = viewport_x + grid_x * cell_size + cell_size // 2
        screen_y = viewport_y + grid_y * cell_size + cell_size // 2
        
        return screen_x, screen_y
    
    def _respect_action_delay(self) -> None:
        """Respecte le délai entre les actions"""
        if self.click_delay > 0:
            elapsed = time.time() - self._last_action_time
            if elapsed < self.click_delay:
                time.sleep(self.click_delay - elapsed)
    
    def _record_action_time(self, action_time: float) -> None:
        """Enregistre le temps d'action pour les statistiques"""
        self._action_times.append(action_time)
        
        # Garder seulement les 100 dernières actions
        if len(self._action_times) > 100:
            self._action_times = self._action_times[-100:]
        
        # Mettre à jour la moyenne
        self._stats.average_action_time = sum(self._action_times) / len(self._action_times)
    
    def get_stats(self) -> NavigationStats:
        """Retourne les statistiques de navigation"""
        with self._lock:
            return NavigationStats(
                total_actions=self._stats.total_actions,
                successful_actions=self._stats.successful_actions,
                failed_actions=self._stats.failed_actions,
                timeout_actions=self._stats.timeout_actions,
                average_action_time=self._stats.average_action_time,
                click_accuracy=self._stats.success_rate
            )
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = NavigationStats()
            self._action_times.clear()
    
    def wait_for_element(self, selector: str, timeout: Optional[float] = None) -> bool:
        """
        Attend qu'un élément soit disponible
        
        Args:
            selector: Sélecteur CSS de l'élément
            timeout: Timeout personnalisé
            
        Returns:
            True si l'élément est trouvé
        """
        if not self.driver or not SELENIUM_AVAILABLE:
            return False
        
        try:
            wait_timeout = timeout or self.action_timeout
            WebDriverWait(self.driver, wait_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return True
        except TimeoutException:
            return False
    
    def take_screenshot(self) -> Optional[bytes]:
        """
        Prend une capture d'écran
        
        Returns:
            Données de l'image en bytes ou None si échec
        """
        if not self.driver or not SELENIUM_AVAILABLE:
            return None
        
        try:
            return self.driver.get_screenshot_as_png()
        except Exception:
            return None


class StubNavigation:
    """
    Implémentation stub pour les tests sans navigateur
    
    Simule les actions de navigation pour les tests unitaires
    """
    
    def __init__(self):
        self.action_log: List[Tuple[str, int, int]] = []
        self._stats = NavigationStats()
    
    def click_cell(self, x: int, y: int) -> bool:
        """Simule un clic simple"""
        self.action_log.append(('click', x, y))
        self._stats.total_actions += 1
        self._stats.successful_actions += 1
        return True
    
    def flag_cell(self, x: int, y: int) -> bool:
        """Simule un flag"""
        self.action_log.append(('flag', x, y))
        self._stats.total_actions += 1
        self._stats.successful_actions += 1
        return True
    
    def double_click_cell(self, x: int, y: int) -> bool:
        """Simule un double-clic"""
        self.action_log.append(('double_click', x, y))
        self._stats.total_actions += 1
        self._stats.successful_actions += 1
        return True
    
    def scroll_to(self, dx: int, dy: int) -> bool:
        """Simule un scroll"""
        self.action_log.append(('scroll', dx, dy))
        self._stats.total_actions += 1
        self._stats.successful_actions += 1
        return True
    
    def get_current_viewport(self) -> Tuple[int, int, int, int]:
        """Retourne un viewport simulé"""
        return (0, 0, 800, 600)
    
    def get_stats(self) -> NavigationStats:
        """Retourne les statistiques simulées"""
        return self._stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        self._stats = NavigationStats()
        self.action_log.clear()
    
    def clear_log(self) -> None:
        """Efface le journal des actions"""
        self.action_log.clear()
