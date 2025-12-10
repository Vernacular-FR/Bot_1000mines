#!/usr/bin/env python3
"""Lanceur direct du Scénario 4 : délègue toute l'init au bot."""


def main():
    print("=== SCÉNARIO 4 DIRECT ===")

    try:
        from bot_1000mines import Minesweeper1000Bot

        bot = Minesweeper1000Bot()

        # Ce lanceur impose la difficulté "impossible" pour reproduire l'ancien comportement
        difficulty = "impossible"

        print("[LANCEUR] Démarrage du scénario 4 (difficulté: impossible)...")
        result = bot.scenario_boucle_jeu_complete(difficulty=difficulty)
        print(f"[LANCEUR] Résultat final: {result}")

    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur.")
    except Exception as e:
        print(f"\nErreur inattendue: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nAppuyez sur Entrée pour quitter...")


if __name__ == "__main__":
    main()
