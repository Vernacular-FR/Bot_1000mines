"""
Contrôleur pour la surcouche UI temps réel dans Selenium.

Gère l'injection et la communication avec BotUI JavaScript.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from selenium.webdriver.remote.webdriver import WebDriver


class UIOverlayType(str, Enum):
    """Types d'overlays disponibles."""
    OFF = "off"
    STATUS = "status"
    ACTIONS = "actions"
    PROBABILITIES = "probabilities"


@dataclass
class StatusCellData:
    """Données d'une cellule pour l'overlay status."""
    col: int
    row: int
    status: str  # UNREVEALED, ACTIVE, FRONTIER, SOLVED, MINE, TO_VISUALIZE


@dataclass
class ActionCellData:
    """Données d'une action pour l'overlay actions."""
    col: int
    row: int
    type: str  # SAFE, FLAG, GUESS
    confidence: float = 1.0


@dataclass
class ProbabilityCellData:
    """Données de probabilité pour l'overlay probas."""
    col: int
    row: int
    probability: float  # 0.0 (safe) à 1.0 (mine)


class UIController:
    """
    Contrôleur de la surcouche UI temps réel.
    
    Injecte et communique avec BotUI.js dans le navigateur.
    """
    
    def __init__(self):
        self._js_code: Optional[str] = None
        self._is_injected = False
        self._bot_running = True
        self._restart_requested = False
    
    def _load_js(self) -> str:
        """Charge le code JavaScript de l'UI."""
        if self._js_code is None:
            js_path = Path(__file__).parent / "overlay_ui.js"
            self._js_code = js_path.read_text(encoding='utf-8')
        return self._js_code
    
    def inject(self, driver: WebDriver) -> bool:
        """
        Injecte l'UI dans la page et l'initialise.
        
        Args:
            driver: Instance Selenium WebDriver
            
        Returns:
            True si succès
        """
        try:
            # Charger et injecter le JS
            js_code = self._load_js()
            driver.execute_script(js_code)
            
            # Initialiser
            result = driver.execute_script("return window.BotUI ? window.BotUI.init() : false;")
            
            if result:
                self._is_injected = True
                print("[UI] Surcouche UI injectée")
                
                # Injecter écouteurs pour détecter les redémarrages manuels
                self._inject_restart_listeners(driver)
            else:
                print("[UI] Échec initialisation UI")
                self._is_injected = False
            
            return self._is_injected
            
        except Exception as e:
            print(f"[UI] Erreur injection: {e}")
            self._is_injected = False
            return False
    
    def _inject_restart_listeners(self, driver: WebDriver) -> None:
        """Injecte des écouteurs pour détecter les redémarrages manuels du jeu."""
        try:
            js_listeners = """
                // Écouter les clics sur les boutons de restart et difficulté
                const restartButtons = document.querySelectorAll('[id*="restart"], [id*="new-game"], button[class*="restart"]');
                const difficultyButtons = document.querySelectorAll('[id*="new-game-"]');
                
                const handleRestart = () => {
                    if (window.__manual_restart_in_progress) return;
                    window.__manual_restart_in_progress = true;
                    window.__manual_restart_requested = true;
                    console.log('[BOT] Redémarrage manuel détecté');
                    setTimeout(() => { window.__manual_restart_in_progress = false; }, 1000);
                };
                
                // Ajouter les écouteurs
                restartButtons.forEach(btn => {
                    if (!btn.hasAttribute('data-bot-listener')) {
                        btn.addEventListener('click', handleRestart);
                        btn.setAttribute('data-bot-listener', 'true');
                    }
                });
                
                difficultyButtons.forEach(btn => {
                    if (!btn.hasAttribute('data-bot-listener')) {
                        btn.addEventListener('click', handleRestart);
                        btn.setAttribute('data-bot-listener', 'true');
                    }
                });
                
                // Observer les changements de score/lives
                if (!window.__bot_game_observer) {
                    let lastScore = -1;
                    let lastLives = -1;
                    
                    window.__bot_game_observer = setInterval(() => {
                        const scoreEl = document.querySelector('[class*="score"], #score');
                        const livesEl = document.querySelector('[class*="lives"], #lives, [class*="life"]');
                        
                        if (scoreEl && livesEl) {
                            const score = parseInt(scoreEl.textContent) || 0;
                            const lives = parseInt(livesEl.textContent) || 0;
                            
                            // Si score=0 et lives=3 (état initial), c'est un redémarrage
                            if (lastScore > 0 && score === 0 && lives === 3) {
                                if (!window.__manual_restart_in_progress) {
                                    window.__manual_restart_in_progress = true;
                                    window.__manual_restart_requested = true;
                                    console.log('[BOT] Redémarrage détecté (score=0, lives=3)');
                                    setTimeout(() => { window.__manual_restart_in_progress = false; }, 1000);
                                }
                            }
                            
                            lastScore = score;
                            lastLives = lives;
                        }
                    }, 500);
                }
            """
            driver.execute_script(js_listeners)
            print("[UI] Écouteurs de redémarrage injectés")
        except Exception as e:
            print(f"[UI] Erreur injection écouteurs: {e}")
    
    def is_ready(self, driver: WebDriver) -> bool:
        """Vérifie si l'UI est injectée et prête."""
        try:
            return driver.execute_script("return typeof window.BotUI !== 'undefined' && window.BotUI.getState().initialized;")
        except Exception:
            return False
    
    def ensure_injected(self, driver: WebDriver) -> bool:
        """S'assure que l'UI est injectée, l'injecte si nécessaire."""
        if not self._is_injected or not self.is_ready(driver):
            return self.inject(driver)
        return True
    
    def set_overlay(self, driver: WebDriver, overlay_type: UIOverlayType) -> bool:
        """Change l'overlay actif."""
        if not self.ensure_injected(driver):
            return False
        
        try:
            driver.execute_script(f"window.BotUI.setOverlay('{overlay_type.value}');")
            return True
        except Exception as e:
            print(f"[UI] Erreur setOverlay: {e}")
            return False
    
    def update_status(self, driver: WebDriver, cells: List[StatusCellData]) -> bool:
        """Met à jour les données de l'overlay status."""
        if not self.ensure_injected(driver):
            return False
        
        try:
            data = {
                'cells': [
                    {'col': c.col, 'row': c.row, 'status': c.status}
                    for c in cells
                ]
            }
            driver.execute_script(f"window.BotUI.updateData('status', {json.dumps(data)});")
            return True
        except Exception as e:
            print(f"[UI] Erreur update_status: {e}")
            return False
    
    def update_actions(self, driver: WebDriver, actions: List[ActionCellData]) -> bool:
        """Met à jour les données de l'overlay actions."""
        if not self.ensure_injected(driver):
            return False
        
        try:
            data = {
                'actions': [
                    {'col': a.col, 'row': a.row, 'type': a.type, 'confidence': a.confidence}
                    for a in actions
                ]
            }
            driver.execute_script(f"window.BotUI.updateData('actions', {json.dumps(data)});")
            return True
        except Exception as e:
            print(f"[UI] Erreur update_actions: {e}")
            return False
    
    def update_probabilities(self, driver: WebDriver, cells: List[ProbabilityCellData]) -> bool:
        """Met à jour les données de l'overlay probabilités."""
        if not self.ensure_injected(driver):
            return False
        
        try:
            data = {
                'cells': [
                    {'col': c.col, 'row': c.row, 'probability': c.probability}
                    for c in cells
                ]
            }
            driver.execute_script(f"window.BotUI.updateData('probabilities', {json.dumps(data)});")
            return True
        except Exception as e:
            print(f"[UI] Erreur update_probabilities: {e}")
            return False
    
    def show_toast(self, driver: WebDriver, message: str, toast_type: str = "info") -> bool:
        """Affiche un toast notification."""
        if not self.ensure_injected(driver):
            return False
        
        try:
            # Échapper le message pour JavaScript
            safe_message = message.replace("'", "\\'").replace('"', '\\"')
            driver.execute_script(f"window.BotUI.showToast('{safe_message}', '{toast_type}');")
            return True
        except Exception as e:
            print(f"[UI] Erreur show_toast: {e}")
            return False
    
    def get_bot_state(self, driver: WebDriver) -> Optional[Dict[str, Any]]:
        """Récupère l'état du bot depuis l'UI."""
        if not self.ensure_injected(driver):
            return None
        
        try:
            return driver.execute_script("return window.BotUI.getState();")
        except Exception as e:
            print(f"[UI] Erreur get_bot_state: {e}")
            return None
    
    def is_bot_running(self, driver: WebDriver) -> bool:
        """Vérifie si le bot est en mode running via l'UI."""
        if not self.is_ready(driver):
            return self._bot_running
        
        try:
            return driver.execute_script("return window.BotUI.isRunning();")
        except:
            return self._bot_running
    
    def is_restart_requested(self, driver: WebDriver) -> bool:
        """Vérifie si un restart a été demandé et reset le flag."""
        if not self.is_ready(driver):
            result = self._restart_requested
            self._restart_requested = False
            return result
        
        try:
            result = driver.execute_script("""
                const flag = window.__botui_restart_requested || false;
                window.__botui_restart_requested = false;
                return flag;
            """)
            return result
        except:
            return False
    
    def is_auto_restart_requested(self, driver: WebDriver) -> bool:
        """Vérifie si un auto-restart (comme 'y') a été demandé."""
        if not self.is_ready(driver):
            return False
        
        try:
            result = driver.execute_script("""
                const flag = window.__botui_auto_restart || false;
                window.__botui_auto_restart = false;
                return flag;
            """)
            return result
        except:
            return False
    
    def is_manual_restart_requested(self, driver: WebDriver) -> bool:
        """Vérifie si un redémarrage manuel (clic bouton) a été détecté."""
        if not self.is_ready(driver):
            return False
        
        try:
            result = driver.execute_script("""
                const flag = window.__manual_restart_requested || false;
                window.__manual_restart_requested = false;
                return flag;
            """)
            return result
        except:
            return False
    
    def set_bot_running(self, driver: WebDriver, running: bool) -> None:
        """Force l'état running du bot dans l'UI."""
        self._bot_running = running
        if not self.is_ready(driver):
            return
        
        try:
            current = driver.execute_script("return window.BotUI.isRunning();")
            if current != running:
                driver.execute_script("window.BotUI.toggleBot();")
        except:
            pass
    
    def destroy(self, driver: WebDriver) -> bool:
        """Détruit l'UI."""
        try:
            driver.execute_script("if (window.BotUI) window.BotUI.destroy();")
            self._is_injected = False
            print("[UI] Surcouche UI détruite")
            return True
        except Exception as e:
            print(f"[UI] Erreur destroy: {e}")
            return False


# Instance globale
_ui_controller: Optional[UIController] = None


def get_ui_controller() -> UIController:
    """Retourne l'instance globale du contrôleur UI."""
    global _ui_controller
    if _ui_controller is None:
        _ui_controller = UIController()
    return _ui_controller
