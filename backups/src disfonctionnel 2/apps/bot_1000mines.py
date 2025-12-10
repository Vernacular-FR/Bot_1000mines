import time


class Minesweeper1000Bot:
    """Coordinateur de scénarios - Architecture réduite aux scénarios critiques."""

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    #  Bloc utilitaire réutilisé par les scénarios 1, 5, 6
    # ------------------------------------------------------------------
    def run_initialization_phase(self, difficulty=None, move=(300, -150), session_service=None):
        """Prépare la session, effectue la navigation initiale et teste l'overlay combiné.
        
        Args:
            difficulty (str, optional): Difficulté du jeu. Defaults to None.
            move (tuple, optional): Déplacement de la vue. Defaults to (150, -100).
        
        Returns:
            dict: {
                'success': bool,
                'session_service': SessionSetupService,
                'nav_move': dict,
                'overlay_result': dict
            }
        """
        from src.services.s1_session_setup_service import SessionSetupService
        from src.services.s1_navigation_service import NavigationService
        from src.services.s1_zone_capture_service import ZoneCaptureService

        result = {
            'success': False,
            'session_service': None,
            'nav_move': None,
            'overlay_result': None
        }

        created_session = False
        if session_service is None:
            session_service = SessionSetupService()
            init_result = session_service.setup_session(difficulty=difficulty)
            if not init_result['success']:
                result['nav_move'] = {'success': False, 'message': init_result['message']}
                return result
            created_session = True
        else:
            # Si une difficulté est forcée alors qu'une session existe déjà, la session appelante reste maître
            if not session_service.is_session_active():
                init_result = session_service.setup_session(difficulty=difficulty)
                if not init_result['success']:
                    result['nav_move'] = {'success': False, 'message': init_result['message']}
                    return result

        nav_service = NavigationService(session_service.get_driver(), session_service)
        print(f"[INIT] Déplacement initial demandé: {move}")
        move_result = nav_service.move_viewport(*move)
        if move_result.get('success'):
            print(f"[INIT] Déplacement initial appliqué: ({move_result.get('dx')}, {move_result.get('dy')})")
        else:
            print(f"[INIT] Échec déplacement initial: {move_result.get('message')}")

        game_paths = None
        game_id = None
        game_session = getattr(session_service, 'game_session', None)
        if game_session and game_session['state'].game_id:
            game_id = game_session['state'].game_id
            try:
                game_paths = game_session['storage'].build_game_paths(game_id)
            except ValueError:
                game_paths = None

        capture_service = ZoneCaptureService(
            driver=session_service.get_driver(),
            paths=game_paths,
            game_id=game_id,
            session_service=session_service
        )

        coord_system = None
        if hasattr(session_service, 'bot') and session_service.bot and hasattr(session_service.bot, 'converter'):
            coord_system = session_service.bot.converter
        else:
            from src.lib.s0_navigation.coordinate_system import CoordinateConverter, GridViewportMapper
            temp_coord_system = CoordinateConverter(driver=session_service.get_driver())
            temp_coord_system.setup_anchor()
            viewport_mapper = GridViewportMapper(temp_coord_system, session_service.get_driver())
            coord_system = temp_coord_system

        test_filename = f"{game_id}_test_interface.png" if game_id else "test_interface.png"
        overlay_result = capture_service.capture_window_with_combined_overlay(
            filename=test_filename,
            overlay_combined=True,
            grid_bounds=(-30, -15, 30, 15),
            viewport_mapper=viewport_mapper if 'viewport_mapper' in locals() else None
        )

        result.update({
            'success': overlay_result.get('success', False),
            'session_service': session_service,
            'nav_move': move_result,
            'overlay_result': overlay_result,
            'created_session': created_session
        })
        return result

    # ------------------------------------------------------------------
    #  Scénarios disponibles
    # ------------------------------------------------------------------
    def scenario_initialisation(self, difficulty=None):
        """Scénario 1: Phase d'initialisation + overlay combiné uniquement."""
        print("\n=== SCÉNARIO 1: Initialisation + Overlay combiné ===")
        init = self.run_initialization_phase(difficulty=difficulty)

        if not init['session_service']:
            print(f"[ERREUR] Initialisation impossible: {init['nav_move']}")
            return False

        if init['nav_move'] and not init['nav_move'].get('success', False):
            print(f"[ATTENTION] Navigation initiale partielle: {init['nav_move'].get('message')}")

        overlay = init['overlay_result'] or {}
        if overlay.get('success'):
            print("[SUCCES] Overlay combiné généré")
            print(f"  Screenshot: {overlay.get('screenshot_path')}")
            print(f"  Overlay: {overlay.get('combined_overlay_path')}")
        else:
            print(f"[ATTENTION] Échec overlay: {overlay.get('message')}")

        return overlay.get('success', False)

    def scenario_analyse_locale(self):
        """Scénario 2: Analyse locale hors navigateur (non implémenté)."""
        # TODO: Ce scénario n'est pas encore défini
        # Il permettra d'effectuer une analyse de grille à partir d'images locales
        # sans avoir besoin d'un navigateur actif
        print("\n=== SCÉNARIO 2: Analyse locale (non implémenté) ===")
        return False

    def scenario_jeu_automatique(self, difficulty=None):
        """Scénario 5: Jeu automatique - une seule passe GameLoop."""
        print("\n=== SCÉNARIO 5: Jeu Automatique (passe unique) ===")

        init = self.run_initialization_phase(difficulty=difficulty)
        if not init['session_service']:
            print(f"[ERREUR] Impossible de lancer la session: {init['nav_move']}")
            return False
        if not init['success']:
            print(f"[ERREUR] Échec de la phase d'initialisation: {init['overlay_result']}")
            return False

        from src.services.s5_game_loop_service import GameLoopService

        session_service = init['session_service']
        game_loop = GameLoopService(
            session_service=session_service,
            max_iterations=1,
            iteration_timeout=30.0,
            delay_between_iterations=1.5,
            game_session=getattr(session_service, 'game_session', None)
        )

        print("[GAME] Exécution d'une passe unique...")
        try:
            pass_result = game_loop.execute_single_pass(iteration_num=1)
            if pass_result['success']:
                print(f"[SUCCES] Passe terminée: {pass_result['message']}")
                return True
            print(f"[ERREUR] Échec de la passe: {pass_result['message']}")
            return False
        except Exception as exc:
            print(f"[ERREUR] Exception pendant la passe: {exc}")
            return False

    def scenario_boucle_jeu_complete(self, session_service=None, difficulty=None):
        """Scénario 6: boucle complète du GameLoopService."""
        print("\n=== SCÉNARIO 6: Boucle de Jeu Automatique ===")

        if session_service is None:
            init = self.run_initialization_phase(difficulty=difficulty)
        else:
            init = self.run_initialization_phase(difficulty=difficulty, session_service=session_service)

        if not init['session_service']:
            print(f"[ERREUR] Impossible de lancer la session: {init['nav_move']}")
            return False
        if not init['success']:
            print(f"[ERREUR] Échec de la phase d'initialisation: {init['overlay_result']}")
            return False
        session_service = init['session_service']

        from src.services.s5_game_loop_service import GameLoopService

        game_loop = GameLoopService(
            session_service=session_service,
            max_iterations=50,
            iteration_timeout=30.0,
            delay_between_iterations=1.5,
            game_session=session_service.game_session
        )

        try:
            result = game_loop.play_game()
            print(f"[FIN] Partie terminée: {result.message}")
            return result.success
        except Exception as exc:
            print(f"[ERREUR] Exception GameLoop: {exc}")
            return False
