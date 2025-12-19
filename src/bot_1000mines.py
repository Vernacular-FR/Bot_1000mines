"""Bot 1000mines - Alternative A refactorisée."""

from __future__ import annotations

from typing import Optional

from src.services import create_session, close_session, run_game, Session


class Minesweeper1000Bot:
    """Bot de démineur avec architecture modulaire Alternative A."""

    def __init__(self):
        self.session: Optional[Session] = None

    def run_minimal_pipeline(
        self,
        difficulty: str = "impossible",
        *,
        overlay_enabled: bool = False,
        max_iterations: int = 500,
        delay_between_iterations: float = 0.2,
    ) -> bool:
        """Pipeline principal : capture → vision → solver → executor."""
        try:
            # Une seule session/navigateur ; le restart clique sur le bouton du jeu
            self.session = create_session(difficulty=difficulty)
            result = run_game(
                self.session,
                max_iterations=max_iterations,
                delay=delay_between_iterations,
                overlay_enabled=overlay_enabled,
            )
            print(f"[GAME] iterations={result['iterations']} actions={result['total_actions']}")
            return result.get("success", False)
        except Exception as e:
            print(f"[ERREUR] {e}")
            # Fermer en cas d'erreur
            if self.session:
                close_session(self.session)
                self.session = None
            return False

    def cleanup(self) -> None:
        """Ferme proprement la session."""
        if self.session:
            close_session(self.session)
            self.session = None
