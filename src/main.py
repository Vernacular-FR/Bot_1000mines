import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.bot_1000mines import Minesweeper1000Bot
from src.config import DIFFICULTY_CONFIG


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline minimal capture → vision")

    parser.add_argument(
        "--difficulty",
        help="Difficulté (parmi: %s)" % ", ".join(DIFFICULTY_CONFIG.keys()),
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="Activer les overlays vision/solver (désactivé par défaut)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=500,
        help="Nombre maximum d'itérations pour résoudre la grille (garde-fou)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Délai entre itérations (secondes) pour laisser les animations/DOM se stabiliser",
    )
    args = parser.parse_args()

    bot = Minesweeper1000Bot()
    success = bot.run_minimal_pipeline(
        args.difficulty,
        overlay_enabled=args.overlay,
        max_iterations=args.max_iterations,
        delay_between_iterations=args.delay,
    )
    bot.cleanup()

    print("[FIN] Succès" if success else "[FIN] Échec")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur.")
    except Exception as e:
        print(f"[ERREUR] Exception non capturée: {e}")
        import traceback
        traceback.print_exc()