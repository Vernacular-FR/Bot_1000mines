"""Service de session : initialisation et cleanup."""

from dataclasses import dataclass
from typing import Optional

from src.lib.s0_browser import BrowserManager, BrowserConfig, BrowserHandle
from src.lib.s0_coordinates import CoordinateConverter, ViewportMapper


@dataclass
class Session:
    """Session active avec tous les composants initialisés."""
    browser: BrowserHandle
    converter: CoordinateConverter
    viewport: ViewportMapper


class SessionService:
    """Gère le cycle de vie d'une session de jeu."""

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self.browser_manager = BrowserManager(self.config)
        self.session: Optional[Session] = None

    def start(self, url: str = "https://1000mines.com") -> Session:
        """Démarre une nouvelle session."""
        # 1. Démarrer le navigateur
        handle = self.browser_manager.start()
        
        # 2. Naviguer vers le jeu
        from src.lib.s0_browser import navigate_to
        navigate_to(handle, url)
        
        # 3. Initialiser le convertisseur de coordonnées
        converter = CoordinateConverter()
        converter.set_driver(handle.driver)
        converter.setup_anchor()
        
        # 4. Initialiser le viewport mapper
        viewport = ViewportMapper(converter, handle.driver)
        
        self.session = Session(
            browser=handle,
            converter=converter,
            viewport=viewport,
        )
        
        return self.session

    def stop(self) -> None:
        """Arrête la session proprement."""
        if self.session and self.session.browser:
            self.browser_manager.stop()
            self.session = None

    def get_session(self) -> Optional[Session]:
        """Retourne la session active."""
        return self.session


# === API fonctionnelle ===

_service: Optional[SessionService] = None


def _get_service() -> SessionService:
    global _service
    if _service is None:
        _service = SessionService()
    return _service


def create_session(url: str = "https://1000mines.com") -> Session:
    """Crée et démarre une nouvelle session."""
    return _get_service().start(url)


def close_session() -> None:
    """Ferme la session active."""
    _get_service().stop()


def get_current_session() -> Optional[Session]:
    """Retourne la session active."""
    return _get_service().get_session()
