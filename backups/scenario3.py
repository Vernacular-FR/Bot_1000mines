#!/usr/bin/env python3
"""Lanceur direct du scénario 3 (une seule passe GameLoop)."""


def main():
    print("=== SCÉNARIO 3 DIRECT ===")

    try:
        from bot_1000mines import Minesweeper1000Bot

        bot = Minesweeper1000Bot()

        difficulty = "impossible"  # aligné sur l'ancien comportement du lanceur direct

        print("[LANCEUR] Exécution du scénario 3 (difficulté: impossible)...")
        result = bot.scenario_jeu_automatique(difficulty=difficulty)
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
