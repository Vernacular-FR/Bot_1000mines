"""
Adaptateur minimal pour lancer les services S0→S6 depuis des scénarios simples.

Ce module se contente d'orchestrer les services présents dans src/services
pour remplacer les anciens scénarios "manuels".
"""

from __future__ import annotations

from typing import Optional

from services.orchestrator import Orchestrator
from services.s1_session_setup_service import SessionSetupService
from services.s5_game_loop_service import GameLoopService


class Minesweeper1000Bot:
    """Point d'entrée scénarios basé sur les nouveaux services."""

    def __init__(self, auto_close_browser: bool = False):
        self.auto_close_browser = auto_close_browser
        self.session_service: Optional[SessionSetupService] = None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _ensure_session(self, difficulty: Optional[str]) -> SessionSetupService:
        if self.session_service and self.session_service.is_session_active():
            return self.session_service

        self.session_service = SessionSetupService(auto_close_browser=self.auto_close_browser)
        result = self.session_service.setup_session(difficulty=difficulty)
        if not result.get("success"):
            raise RuntimeError(f"Configuration de session impossible: {result.get('message')}")
        return self.session_service

    def cleanup(self) -> None:
        if self.session_service:
            self.session_service.cleanup_session()
            self.session_service = None

    # ------------------------------------------------------------------ #
    # Scénarios
    # ------------------------------------------------------------------ #
    def scenario_orchestrator_direct(self, iterations: int = 1, difficulty: Optional[str] = None) -> bool:
        """Lance le nouvel Orchestrator sur N itérations."""
        session = self._ensure_session(difficulty)
        orchestrator = Orchestrator(session_service=session, enable_metrics=False)

        if not orchestrator.initialize(difficulty=difficulty):
            print("❌ Orchestrator : initialisation échouée")
            return False

        try:
            for idx in range(iterations):
                print(f"\n🎯 Itération orchestrateur {idx + 1}/{iterations}")
                result = orchestrator.run_game_iteration()
                print(f"➡️ Résultat: {result}")
                if not result.get("success"):
                    return False
            return True
        finally:
            orchestrator.shutdown()

    def scenario_game_loop(self, iterations: int = 5, difficulty: Optional[str] = None) -> bool:
        """Utilise GameLoopService (S5) pour enchaîner les itérations classiques."""
        session = self._ensure_session(difficulty)
        loop = GameLoopService(
            session_service=session,
            max_iterations=iterations,
            iteration_timeout=30.0,
            delay_between_iterations=1.0,
            game_session=getattr(session, "game_session", None),
        )

        try:
            result = loop.play_game()
            print(f"[GAME LOOP] Terminé: {result.message}")
            return result.success
        except Exception as exc:
            print(f"[GAME LOOP] Erreur: {exc}")
            return False
