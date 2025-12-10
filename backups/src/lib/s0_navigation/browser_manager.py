"""
BrowserManager (S0) - Gestionnaire Selenium centralisé

Ce module remplace l'ancien BrowserManager de lib.s1_interaction pour la
nouvelle architecture S0 Navigation. Il encapsule la création du driver
Chrome, l'application des options issues de lib.config et expose des
méthodes simples pour démarrer, naviguer et arrêter le navigateur.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from webdriver_manager.chrome import ChromeDriverManager

from lib.config import BROWSER_CONFIG, WAIT_TIMES


class BrowserManager:
    """Gère tout le cycle de vie du navigateur Chrome pour S0."""

    def __init__(self) -> None:
        self.driver: Optional[webdriver.Chrome] = None
        self.is_started = False

    def _build_options(self) -> Options:
        """Construit les options Chrome à partir de la configuration."""
        options = Options()

        # Mode headless
        if BROWSER_CONFIG.get("headless", False):
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")

        # Démarrage maximisé (remplace maximize_window pour éviter les sauts)
        if BROWSER_CONFIG.get("maximize", True):
            options.add_argument("--start-maximized")

        # User agent custom
        user_agent = BROWSER_CONFIG.get("user_agent")
        if user_agent:
            options.add_argument(f"--user-agent={user_agent}")

        # Options de stabilité
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")

        # Répertoire utilisateur isolé si fourni
        profile_dir = BROWSER_CONFIG.get("profile_dir")
        if profile_dir:
            Path(profile_dir).mkdir(parents=True, exist_ok=True)
            options.add_argument(f"--user-data-dir={profile_dir}")

        return options

    def start_browser(self) -> bool:
        """Lance Chrome avec les options configurées."""
        if self.is_started and self.driver:
            return True

        try:
            print("🔧 BrowserManager: installation du driver Chrome...")
            service = Service(ChromeDriverManager().install())

            print("🔧 BrowserManager: démarrage de Chrome...")
            self.driver = webdriver.Chrome(service=service, options=self._build_options())
            self.is_started = True
            return True

        except WebDriverException as exc:
            print(f"[ERREUR] Démarrage Chrome impossible: {exc}")
            self.driver = None
            self.is_started = False
            return False

    def get_driver(self) -> Optional[webdriver.Chrome]:
        """Retourne l'instance Selenium active."""
        return self.driver

    def navigate_to(self, url: str) -> bool:
        """Navigue vers une URL et attend que le body soit présent."""
        if not self.driver or not self.is_started:
            print("[ERREUR] Navigateur non démarré")
            return False

        try:
            self.driver.get(url)
            WebDriverWait(self.driver, WAIT_TIMES.get("page_load", 10)).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            return True

        except TimeoutException:
            print("[ERREUR] Timeout lors du chargement de la page")
            return False
        except WebDriverException as exc:
            print(f"[ERREUR] Navigation impossible: {exc}")
            return False

    def stop_browser(self) -> None:
        """Ferme le navigateur proprement."""
        if self.driver:
            self.driver.quit()
            self.driver = None
        self.is_started = False
