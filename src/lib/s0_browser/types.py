"""Types pour le module s0_browser."""

from dataclasses import dataclass
from typing import Optional, Any
from selenium.webdriver.remote.webdriver import WebDriver


@dataclass
class BrowserConfig:
    """Configuration du navigateur."""
    headless: bool = False
    maximize: bool = True
    url: str = "https://1000mines.com"
    user_agent: Optional[str] = None
    page_load_timeout: int = 10


@dataclass
class BrowserHandle:
    """Handle vers un navigateur actif."""
    driver: WebDriver
    is_started: bool = True
    
    def execute_js(self, script: str, *args) -> Any:
        """Exécute un script JavaScript."""
        return self.driver.execute_script(script, *args)
    
    def close(self) -> None:
        """Ferme le navigateur."""
        if self.driver:
            self.driver.quit()
            self.is_started = False
