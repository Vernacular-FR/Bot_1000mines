from __future__ import annotations

from typing import Dict, List
from pathlib import Path

from src.services.s1_session_setup_service import SessionSetupService
from src.services.s5_game_loop_service import GameLoopService


class Minesweeper1000Bot:
    """
    Scénario minimal : session → boucle unique via GameLoopService (capture → vision → storage → solver → action).
    """

    def __init__(self):
        self.session_service = SessionSetupService(auto_close_browser=True)
        # La fermeture effective est pilotée par le script principal (main/loop).
        self.session_service.auto_close_browser = False

    def run_minimal_pipeline(
        self,
        difficulty: str | None = None,
        *,
        overlay_enabled: bool = False,
        max_iterations: int = 80,
        delay_between_iterations: float = 0.2,
    ) -> bool:
        """Pipeline principal : boucle via GameLoopService jusqu'à fin de partie (ou max_iterations)."""
        init = self.session_service.setup_session(difficulty)
        if not init.get("success"):
            print(f"[SESSION] Échec init: {init.get('message')}")
            return False

        loop = GameLoopService(
            session_service=self.session_service,
            max_iterations=max_iterations,
            iteration_timeout=60.0,
            delay_between_iterations=delay_between_iterations,
            overlay_enabled=overlay_enabled,
            execute_actions=True,
        )
        result = loop.play_game()
        print(
            f"[GAME] success={result.success} final_state={getattr(result.final_state, 'value', result.final_state)} "
            f"iterations={result.iterations} actions_executed={result.actions_executed}"
        )
        return bool(result.success)

    def cleanup(self) -> None:
        """Ferme proprement la session/navigateur (demande Entrée)."""
        try:
            self.session_service.cleanup_session()
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[CLEANUP] Erreur lors du cleanup de session: {exc}")
