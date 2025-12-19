"""Service de session : initialisation et nettoyage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.lib.s0_browser import BrowserConfig, BrowserHandle, start_browser, stop_browser, navigate_to
from src.lib.s0_browser.game_info import GameInfoExtractor
from src.lib.s0_coordinates import CoordinateConverter, ViewportMapper, CanvasLocator
from src.lib.s3_storage import StorageController
from src.config import DIFFICULTY_CONFIG


@dataclass
class Session:
    """Session de jeu active."""
    browser: BrowserHandle
    storage: StorageController
    converter: CoordinateConverter
    viewport: ViewportMapper
    canvas_locator: CanvasLocator
    extractor: GameInfoExtractor
    game_id: Optional[str] = None
    difficulty: Optional[str] = None
    is_exploring: bool = False
    exploration_start_lives: int = 0
    last_state: Optional[int] = None
    same_state_count: int = 0

    @property
    def driver(self):
        return self.browser.driver


_current_session: Optional[Session] = None


def create_session(
    difficulty: str = "impossible",
    headless: bool = False,
) -> Session:
    """Crée une nouvelle session de jeu."""
    global _current_session
    
    # 1. Démarrer le navigateur
    config = BrowserConfig(headless=headless)
    browser = start_browser(config)
    
    # 2. Naviguer vers le jeu
    url = f"https://1000mines.com/?level={difficulty}"
    navigate_to(browser, url)
    driver = browser.driver
    wait = WebDriverWait(driver, 10)

    # 2.0 Sélectionner systématiquement le mode Infinite (mode de jeu) comme dans le legacy
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/#infinite']")))
        infinite_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/#infinite'] button"))
        )
        infinite_button.click()
        print("   - Mode Infinite sélectionné")
    except Exception as e:
        print(f"[AVERTISSEMENT] Impossible de sélectionner le mode Infinite: {e}")

    # 2.1 Sélectionner la difficulté via Selenium (avec fallback JS)
    selenium_id = DIFFICULTY_CONFIG.get(difficulty, {}).get("selenium_id")
    if selenium_id:
        try:
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"#{selenium_id}")))
            driver.execute_script("arguments[0].click();", element)
            print(f"   - Difficulté {difficulty} sélectionnée")
        except Exception as e:
            print(f"   - Échec sélection Selenium, tentative JS: {e}")
            try:
                driver.execute_script(f"document.querySelector('#{selenium_id}')?.click();")
                print(f"   - Difficulté {difficulty} sélectionnée via JS")
            except Exception as e_js:
                print(f"   - Erreur lors de la sélection de la difficulté: {e_js}")
    
    # 3. Initialiser les composants
    converter = CoordinateConverter()
    converter.set_driver(browser.driver)
    converter.setup_anchor()  # Initialiser l'anchor pour les conversions de coordonnées
    
    viewport = ViewportMapper(converter, browser.driver)
    canvas_locator = CanvasLocator(driver=browser.driver)
    storage = StorageController()
    extractor = GameInfoExtractor(driver=browser.driver)
    
    # 4. Créer la session
    session = Session(
        browser=browser,
        storage=storage,
        converter=converter,
        viewport=viewport,
        canvas_locator=canvas_locator,
        extractor=extractor,
        difficulty=difficulty,
    )
    
    _current_session = session
    print(f"[SESSION] Session créée pour difficulté: {difficulty}")
    return session


def close_session(session: Optional[Session] = None) -> None:
    """Ferme une session proprement."""
    global _current_session
    
    session = session or _current_session
    if session and session.browser:
        stop_browser(session.browser)
        print("[SESSION] Session fermée")
    
    if session == _current_session:
        _current_session = None


def get_current_session() -> Optional[Session]:
    """Retourne la session courante."""
    return _current_session


def restart_game(session: Session) -> None:
    """Clique sur le bouton restart du jeu et réinitialise le storage."""
    driver = session.driver
    wait = WebDriverWait(driver, 10)
    try:
        restart_host = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#ctl-restart-host"))
        )
        # Essayer d'abord le bouton enfant, sinon le host lui-même
        driver.execute_script(
            """
const host = arguments[0];
const btn = host.querySelector('button') || host;
btn.scrollIntoView({block: 'center', inline: 'center'});
btn.click();
btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
""",
            restart_host,
        )
        print("[SESSION] Restart du jeu via JS sur ctl-restart-host")
    except Exception as e:
        print(f"[AVERTISSEMENT] Impossible de cliquer sur le bouton restart: {e}")
    # Reset du storage pour la nouvelle partie
    session.storage = StorageController()
