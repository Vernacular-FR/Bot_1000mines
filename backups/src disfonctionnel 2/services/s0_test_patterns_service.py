"""
Service de test patterns pour le bot Minesweeper 1000mines.
Effectue des tests de marquage avec des drapeaux sur les coins du viewport.
"""

import time
import sys
import os

# Import du système de logging centralisé
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Logs.logger import save_bot_log

# Imports des modules du bot
from src.lib.s0_navigation.game_controller import NavigationController
from src.lib.s0_navigation.coordinate_system import CoordinateConverter, GridViewportMapper


class TestPatternsService:
    """Service pour tester les patterns de marquage avec drapeaux du bot."""
    
    def __init__(self, driver, session_service=None):
        """
        Initialise le service de test patterns.
        
        Args:
            driver: Instance WebDriver pour interagir avec le jeu
            session_service: Instance SessionSetupService déjà configurée (optionnel)
        """
        self.driver = driver
        self.game_bot = None
        self.coord_system = None
        self.test_results = []
        
        # Récupérer les composants depuis SessionSetupService
        self._get_components_from_session(session_service)
    
    def _get_components_from_session(self, session_service=None):
        """Récupère les composants depuis SessionSetupService."""
        try:
            # Utiliser le session_service fourni ou en créer un nouveau
            if session_service is None:
                from src.services.session_setup_service import SessionSetupService
                session_service = SessionSetupService()
            
            # Récupérer les composants directement sans vérifier is_initialized
            # car la session peut être configurée mais is_initialized False
            try:
                self.game_bot = session_service.navigation_controller
                self.coord_system = self.game_bot.converter if hasattr(self.game_bot, 'converter') else None
            except:
                # Si l'accès direct échoue, retourner une erreur
                print("[ERREUR] Impossible d'accéder aux contrôleurs de navigation")
                self.game_bot = None
                self.coord_system = None
                return
            
            if self.game_bot and self.coord_system:
                print("[SUCCES] Composants récupérés depuis SessionSetupService")
            else:
                print("[ERREUR] Impossible de récupérer les composants")
                print(f"[DEBUG] game_bot: {self.game_bot}")
                print(f"[DEBUG] coord_system: {self.coord_system}")
                
        except Exception as e:
            print(f"[ERREUR] Erreur récupération composants: {e}")
            import traceback
            traceback.print_exc()
        
        
    def test_viewport_corners(self):
        """
        Test uniquement le placement des drapeaux sur les 4 coins du viewport.
        
        Returns:
            dict: Résultat du test {
                'success': bool,
                'message': str,
                'flags_count': int,
                'details': dict
            }
        """
        print("\n=== DÉBUT DU TEST COINS ===")
        print("Test: Placement des 4 angles du viewport avec des drapeaux")
        
        test_start_time = time.time()
        flags_count = 0
        details = {
            'flags': [],
            'errors': []
        }
        
        try:
            if not self.game_bot or not self.coord_system:
                return {
                    'success': False,
                    'message': "Composants non fournis - game_bot ou coord_system manquant",
                    'flags_count': 0,
                    'details': details
                }
            
            print("[SUCCES] Composants disponibles")
            
            # Obtenir les coins du viewport
            print("\n[PHASE 1] Calcul des coins du viewport...")
            corners = self.coord_system.get_viewport_corners()
            
            if not corners:
                return {
                    'success': False,
                    'message': "Impossible d'obtenir les coordonnées des coins du viewport",
                    'flags_count': 0,
                    'details': details
                }
            
            # Placer un drapeau à chaque coin
            print("\n[PHASE 2] Placement des drapeaux...")
            corner_positions = [
                ('coin_sup_gauche', corners['top_left']),
                ('coin_sup_droit', corners['top_right']),
                ('coin_inf_gauche', corners['bottom_left']),
                ('coin_inf_droit', corners['bottom_right'])
            ]
            
            for corner_name, (x, y) in corner_positions:
                print(f"[DRAPEAU] Placement au {corner_name}...")
                flag_result = self.game_bot.click_cell(x, y, right_click=True)
                
                if flag_result:
                    flags_count += 1
                    details['flags'].append({
                        'corner': corner_name,
                        'grid_x': x,
                        'grid_y': y,
                        'success': True
                    })
                    print(f"[SUCCES] Drapeau placé au {corner_name}")
                else:
                    details['errors'].append(f"Échec {corner_name}: ({x}, {y})")
                    print(f"[ERREUR] Échec du placement au {corner_name}: ({x}, {y})")
            
            test_duration = time.time() - test_start_time
            
            return {
                'success': flags_count > 0,
                'message': f"Test terminé en {test_duration:.2f}s - {flags_count}/4 drapeaux placés",
                'flags_count': flags_count,
                'details': details
            }
            
        except Exception as e:
            print(f"[ERREUR] Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f"Erreur critique: {e}",
                'flags_count': flags_count,
                'details': details
            }
    
        
    
