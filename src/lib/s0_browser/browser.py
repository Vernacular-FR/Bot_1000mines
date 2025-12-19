"""Gestion du navigateur Selenium."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from .types import BrowserConfig, BrowserHandle


class BrowserManager:
    """Gestionnaire du navigateur web."""

    def __init__(self, config: BrowserConfig = None):
        self.config = config or BrowserConfig()
        self.handle: BrowserHandle = None

    def start(self) -> BrowserHandle:
        """Démarre le navigateur Chrome."""
        try:
            options = Options()

            if self.config.headless:
                options.add_argument("--headless")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")

            if self.config.maximize:
                options.add_argument("--start-maximized")

            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            if self.config.user_agent:
                options.add_argument(f'user-agent={self.config.user_agent}')

            print("1. Installation du pilote Chrome...")
            service = Service(ChromeDriverManager().install())
            
            print("2. Démarrage de Chrome...")
            driver = webdriver.Chrome(service=service, options=options)
            
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            if self.config.maximize and not self.config.headless:
                driver.maximize_window()

            print("3. Navigateur démarré avec succès!")
            self.handle = BrowserHandle(driver=driver, is_started=True)
            return self.handle

        except WebDriverException as e:
            print(f"[ERREUR] Erreur lors du démarrage du navigateur: {e}")
            raise

    def stop(self) -> None:
        """Arrête le navigateur proprement."""
        if self.handle and self.handle.driver:
            self.handle.driver.quit()
            self.handle.is_started = False
            print("[FIN] Navigateur arrêté")

    def get_handle(self) -> BrowserHandle:
        """Retourne le handle actif."""
        return self.handle


def start_browser(config: BrowserConfig = None) -> BrowserHandle:
    """Démarre un navigateur et retourne un handle."""
    manager = BrowserManager(config)
    return manager.start()


def stop_browser(handle: BrowserHandle) -> None:
    """Arrête un navigateur via son handle."""
    if handle:
        handle.close()


def navigate_to(handle: BrowserHandle, url: str, timeout: int = 10) -> bool:
    """Navigue vers une URL."""
    if not handle or not handle.is_started:
        print("[ERREUR] Navigateur non démarré")
        return False

    try:
        print(f"[NAVIGATION] Navigation vers: {url}")
        handle.driver.get(url)

        WebDriverWait(handle.driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        print("[SUCCES] Page chargée avec succès")
        return True

    except TimeoutException:
        print("[ERREUR] Timeout lors du chargement de la page")
    except Exception as e:
        print(f"[ERREUR] Erreur lors de la navigation: {e}")
    return False
