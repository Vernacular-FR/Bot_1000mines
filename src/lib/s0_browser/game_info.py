"""Extraction des informations de jeu depuis le DOM (score, vie, etc.)."""

from dataclasses import dataclass
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from .types import BrowserHandle

@dataclass
class GameInfo:
    """Informations sur l'état du jeu extraites du DOM."""
    score: int = 0
    lives: int = 1
    high_score: int = 0
    mode: str = "unknown"

class GameInfoExtractor:
    """Extrait les informations de jeu depuis le navigateur."""

    def __init__(self, driver: WebDriver):
        self.driver = driver

    def get_game_info(self) -> GameInfo:
        """Récupère les informations actuelles du jeu."""
        try:
            # Score
            score_el = self.driver.find_element(By.ID, "score")
            score = int(score_el.text) if score_el.text.isdigit() else 0
            
            # High Score
            high_el = self.driver.find_element(By.ID, "high")
            high_score = int(high_el.text) if high_el.text.isdigit() else 0
            
            # Mode
            mode_el = self.driver.find_element(By.ID, "mode")
            mode = mode_el.text
            
            # Lives (Health) - Compter les coeurs
            health_el = self.driver.find_element(By.ID, "helth") # Sic: "helth" dans le DOM
            lives = health_el.text.count("♥")
            
            return GameInfo(
                score=score,
                lives=lives,
                high_score=high_score,
                mode=mode
            )
        except Exception as e:
            print(f"[GameInfo] Erreur extraction: {e}")
            return GameInfo()
