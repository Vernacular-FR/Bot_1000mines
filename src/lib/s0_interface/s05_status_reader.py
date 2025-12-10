from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from .api import GameStatus


@dataclass
class StatusPanelSnapshot:
    """Structure interne détaillant ce qui est lu dans #status."""

    raw: Dict[str, Optional[str]]
    timestamp: datetime


class StatusReader:
    """
    Interroge le panneau `#status` pour extraire difficulté, scores, vies et bonus.
    Cette classe se limite à Selenium et renvoie un `GameStatus` utilisable par les couches supérieures.
    """

    STATUS_SELECTOR = "div#status"
    FIELD_SELECTORS = {
        "difficulty": "#mode",
        "high_score": "#high",
        "current_score": "#score",
        "bonus_counter": "#things",
        "lives": "#helth",
    }
    BONUS_THRESHOLD = 1000  # Observé sur le site : +1 vie par tranche de 1000 points

    def __init__(self, driver: WebDriver, wait_timeout: float = 5.0):
        self.driver = driver
        self.wait_timeout = wait_timeout

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def read_status(self) -> GameStatus:
        snapshot = self._capture_panel()

        parsed = {
            "difficulty": snapshot.raw.get("difficulty"),
            "high_score": self._parse_int(snapshot.raw.get("high_score")),
            "current_score": self._parse_int(snapshot.raw.get("current_score")),
            "bonus_counter": self._parse_int(snapshot.raw.get("bonus_counter")),
            "lives_display": snapshot.raw.get("lives") or "",
        }

        lives = self._count_lives(parsed["lives_display"])

        return GameStatus(
            difficulty=parsed["difficulty"],
            high_score=parsed["high_score"],
            current_score=parsed["current_score"],
            lives=lives,
            lives_display=parsed["lives_display"],
            bonus_counter=parsed["bonus_counter"],
            bonus_threshold=self.BONUS_THRESHOLD,
            raw_snapshot=snapshot.raw,
            captured_at=snapshot.timestamp,
        )

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _capture_panel(self) -> StatusPanelSnapshot:
        self._ensure_status_present()

        dom_payload = self.driver.execute_script(
            """
            const rootSelector = arguments[0];
            const root = document.querySelector(rootSelector);
            if (!root) {
                return null;
            }

            const readText = (selector) => {
                if (!selector) return null;
                const scoped = root.querySelector(selector);
                if (scoped) {
                    return scoped.textContent.trim();
                }
                const globalEl = document.querySelector(selector);
                return globalEl ? globalEl.textContent.trim() : null;
            };

            const payload = {
                difficulty: readText("#mode") || root.getAttribute("data-mode") || null,
                high_score: readText("#high"),
                current_score: readText("#score"),
                bonus_counter: readText("#things") || readText(".things"),
                lives: readText("#helth") || readText(".helth"),
                raw_text: root.innerText,
            };
            return payload;
            """,
            self.STATUS_SELECTOR,
        )

        if dom_payload is None:
            raise RuntimeError("Impossible de lire le panneau #status.")

        return StatusPanelSnapshot(raw=dom_payload, timestamp=datetime.utcnow())

    def _ensure_status_present(self) -> None:
        WebDriverWait(self.driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, self.STATUS_SELECTOR))
        )

    @staticmethod
    def _parse_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        sanitized = "".join(ch for ch in value if ch.isdigit())
        if not sanitized:
            return None
        try:
            return int(sanitized)
        except ValueError:
            return None

    @staticmethod
    def _count_lives(display: str) -> Optional[int]:
        if display is None:
            return None
        stripped = display.strip()
        if not stripped:
            return None
        # Certains modes affichent un nombre (ex: "x3") : tenter la conversion directe
        numeric = StatusReader._parse_int(stripped)
        if numeric is not None:
            return numeric

        # Sinon, compter le nombre de symboles (cœurs, etc.)
        symbols = [ch for ch in stripped if not ch.isspace()]
        return len(symbols) if symbols else None
