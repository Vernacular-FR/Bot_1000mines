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
    args = parser.parse_args()

    bot = Minesweeper1000Bot()
    success = bot.run_minimal_pipeline(args.difficulty, overlay_enabled=args.overlay)
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