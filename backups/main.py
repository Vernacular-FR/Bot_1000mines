"""
Point d'entrée principal pour le bot 1000mines.

Ce launcher utilise le nouvel Orchestrator S0→S6 alimenté par
SessionSetupService sans passer par les anciens adaptateurs.
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root / "src"))
sys.path.append(str(project_root / "_old"))

from services.orchestrator import Orchestrator  # noqa: E402
from services.s1_session_setup_service import SessionSetupService  # noqa: E402


def run_orchestrator(iterations: int, difficulty: str | None) -> int:
    """
    Lance l'orchestrateur direct et exécute N itérations.

    Args:
        iterations: nombre d'itérations à enchaîner.
        difficulty: difficulté transmise à la phase d'initialisation.
    """
    session_service = SessionSetupService(auto_close_browser=True)
    orchestrator = Orchestrator(session_service=session_service, enable_metrics=True)

    print("🚀 Lancement orchestrateur en mode DIRECT")
    if not orchestrator.initialize(difficulty=difficulty):
        print("❌ Initialisation échouée")
        session_service.cleanup_session()
        return 1

    try:
        for turn in range(iterations):
            print(f"\n🎯 Itération {turn + 1}/{iterations}")
            result = orchestrator.run_game_iteration()
            print(f"➡️  Résultat: {result}")

            if not result.get("success", False):
                print("⚠️ Arrêt anticipé suite à un échec d'itération")
                break
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par l'utilisateur.")
    finally:
        orchestrator.shutdown()

    return 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launcher direct pour l'orchestrateur S0-S6."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Nombre d'itérations à exécuter (par défaut: 1).",
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        default=None,
        help="Difficulté transmise à l'orchestrateur (beginner/intermediate/expert).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    return run_orchestrator(
        iterations=max(1, args.iterations), difficulty=args.difficulty
    )


if __name__ == "__main__":
    raise SystemExit(main())
