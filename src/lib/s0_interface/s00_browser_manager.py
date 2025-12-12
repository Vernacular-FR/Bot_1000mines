from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from typing import Optional

from src.config import BROWSER_CONFIG, WAIT_TIMES


class BrowserManager:
    """Gestionnaire complet du navigateur web"""

    def __init__(self):
        self.driver = None
        self.is_started = False

    def start_browser(self) -> bool:
        """Démarre le navigateur Chrome avec les options de configuration."""
        try:
            options = Options()

            # Configuration du mode headless si nécessaire
            if BROWSER_CONFIG.get("headless", False):
                options.add_argument("--headless")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")

            # Configuration du mode plein écran
            if BROWSER_CONFIG.get('maximize', True):
                options.add_argument("--start-maximized")

            # Options de sécurité et de discrétion
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            # Configuration de l'user-agent
            if "user_agent" in BROWSER_CONFIG:
                options.add_argument(f'user-agent={BROWSER_CONFIG["user_agent"]}')

            print("1. Installation du pilote Chrome...")
            service = Service(ChromeDriverManager().install())
            
            print("2. Démarrage de Chrome...")
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Masquer les indicateurs d'automatisation
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # Si le mode plein écran est activé mais que le mode headless est désactivé
            if BROWSER_CONFIG.get('maximize', True) and not BROWSER_CONFIG.get('headless', False):
                self.driver.maximize_window()

            print("3. Navigateur démarré avec succès!")
            self.is_started = True
            return True

        except WebDriverException as e:
            print(f"[ERREUR] Erreur lors du démarrage du navigateur: {e}")
            return False

    def get_driver(self):
        """Retourne l'instance du driver Selenium."""
        return self.driver

    def navigate_to(self, url: str) -> bool:
        """
        Navigue vers une URL spécifique
        
        Args:
            url: URL cible
            
        Returns:
            bool: True si succès, False si échec
        """
        if not self.is_started or not self.driver:
            print("[ERREUR] Navigateur non démarré")
            return False

        try:
            print(f"[NAVIGATION] Navigation vers: {url}")
            self.driver.get(url)

            # Attendre que la page se charge
            WebDriverWait(self.driver, WAIT_TIMES.get('page_load', 10)).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            print("[SUCCES] Page chargee avec succes")
            return True

        except TimeoutException:
            print("[ERREUR] Timeout lors du chargement de la page")
        except Exception as e:
            print(f"[ERREUR] Erreur lors de la navigation: {e}")
        return False


    def stop_browser(self):
        """Arrête le navigateur proprement"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.is_started = False
            print("[FIN] Navigateur arrêté")
