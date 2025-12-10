import argparse
from typing import Callable

from src.apps.bot_1000mines import Minesweeper1000Bot


SCENARIO_MAP: dict[str, tuple[str, bool]] = {
    "1": ("scenario_initialisation", True),
    "2": ("scenario_analyse_locale", False),
    "3": ("scenario_jeu_automatique", True),
    "4": ("scenario_boucle_jeu_complete", True),
}


def _ask_difficulty() -> str:
    """Boucle tant qu'une difficulté valide n'est pas renseignée."""
    while True:
        value = input("Choisissez la difficulté (ex: beginner, impossible): ").strip()
        if value:
            return value
        print("Veuillez renseigner une difficulté.")


def _run_scenario(scenario_id: str, difficulty: str | None) -> None:
    scenario = SCENARIO_MAP.get(scenario_id)
    if not scenario:
        raise ValueError(f"Scénario inconnu: {scenario_id}")

    method_name, requires_difficulty = scenario
    chosen_difficulty = difficulty
    if requires_difficulty and not chosen_difficulty:
        chosen_difficulty = _ask_difficulty()

    bot = Minesweeper1000Bot()
    scenario_callable: Callable = getattr(bot, method_name)

    if requires_difficulty:
        scenario_callable(difficulty=chosen_difficulty)
    else:
        scenario_callable()


def _interactive_menu():
    print("=== Lanceur 1000mines.com ===")
    print("1. Scénario 1: Initialisation + overlay combiné")
    print("2. Scénario 2: Analyse locale (sans navigateur)")
    print("3. Scénario 3: Jeu automatique (passe unique)")
    print("4. Scénario 4: Boucle de jeu complète (GameLoopService)")
    print("5. Quitter\n")

    while True:
        choix = input("Votre choix (1-5): ").strip()

        if choix in SCENARIO_MAP:
            _run_scenario(choix, None)
        elif choix in ("5", "q", "Q"):
            print("\nAu revoir !")
            break
        else:
            print("Choix invalide. Merci de sélectionner une option listée.")


def main():
    parser = argparse.ArgumentParser(description="Lanceur du bot 1000mines.com")
    parser.add_argument("--scenario", choices=SCENARIO_MAP.keys(), help="Scénario à exécuter (1-4)")
    parser.add_argument("--difficulty", help="Difficulté à appliquer (utilisé pour les scénarios 1, 3, 4)")
    args = parser.parse_args()

    try:
        if args.scenario:
            _run_scenario(args.scenario, args.difficulty)
        else:
            _interactive_menu()
    except KeyboardInterrupt:
        print("\n\nArrêt demandé par l'utilisateur.")
    except Exception as e:
        print(f"\nErreur critique: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    try:
        while True:
            main()
            if input("\nVoulez-vous effectuer une autre opération ? (o/n): ").lower() != 'o':
                print("\nAu revoir !")
                break
    except KeyboardInterrupt:
        print("\n\nArrêt demandé par l'utilisateur.")
    except Exception as e:
        print(f"\nErreur critique: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup final déclenché par l'appui sur Entrée
    input("\nAppuyez sur Entrée pour fermer le navigateur et quitter...")
    
    # Tenter de nettoyer une session éventuellement laissée ouverte
    try:
        from src.services.s1_session_setup_service import SessionSetupService
        session = SessionSetupService(auto_close_browser=True)  # Force la fermeture
        session.cleanup_session()
    except:
        pass  # Pas de session à nettoyer