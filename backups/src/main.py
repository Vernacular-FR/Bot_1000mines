from bot_1000mines import Minesweeper1000Bot


def _ask_difficulty(prompt="Choisissez la difficulté (laisser vide pour demande interactive): "):
    user_choice = input(prompt).strip()
    return user_choice or None


def main():
    print("=== Lanceur 1000mines.com ===")
    print("1. Scénario 1: Initialisation + overlay combiné")
    print("2. Scénario 2: Analyse locale (sans navigateur)")
    print("3. Scénario 3: Jeu automatique (passe unique)")
    print("4. Scénario 4: Boucle de jeu complète (GameLoopService)")
    print("5. Quitter\n")

    choix = input("Votre choix (1-5): ").strip()

    if choix == '1':
        try:
            bot = Minesweeper1000Bot()
            diff = _ask_difficulty()
            bot.scenario_initialisation(difficulty=diff)
        except KeyboardInterrupt:
            print("\nArrêt demandé par l'utilisateur.")
        except Exception as e:
            print(f"\nErreur inattendue: {e}")
            import traceback
            traceback.print_exc()

    elif choix == '2':
        try:
            bot = Minesweeper1000Bot()
            bot.scenario_analyse_locale()
        except KeyboardInterrupt:
            print("\nArrêt demandé par l'utilisateur.")
        except Exception as e:
            print(f"\nErreur inattendue: {e}")
            import traceback
            traceback.print_exc()

    elif choix == '3':
        try:
            bot = Minesweeper1000Bot()
            diff = _ask_difficulty()
            bot.scenario_jeu_automatique(difficulty=diff)
        except KeyboardInterrupt:
            print("\nArrêt demandé par l'utilisateur.")
        except Exception as e:
            print(f"\nErreur inattendue: {e}")
            import traceback
            traceback.print_exc()

    elif choix == '4':
        try:
            bot = Minesweeper1000Bot()
            diff = _ask_difficulty()
            bot.scenario_boucle_jeu_complete(difficulty=diff)
        except KeyboardInterrupt:
            print("\nArrêt demandé par l'utilisateur.")
        except Exception as e:
            print(f"\nErreur inattendue: {e}")
            import traceback
            traceback.print_exc()

    elif choix == '5' or choix.lower() == 'q':
        print("\nAu revoir !")
        return
    else:
        print("\nChoix invalide. Veuillez réessayer.")
        main()

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
        from services.s1_session_setup_service import SessionSetupService
        session = SessionSetupService(auto_close_browser=True)  # Force la fermeture
        session.cleanup_session()
    except:
        pass  # Pas de session à nettoyer