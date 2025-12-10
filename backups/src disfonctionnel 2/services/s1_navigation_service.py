"""
Service de Navigation - Mouvements simples de la vue

Service dédié aux mouvements de base du viewport sans logique de test complexe.
Utilisé pour les scénarios qui nécessitent un déplacement avant capture.
"""

from src.lib.s0_navigation.game_controller import NavigationController
from src.lib.s0_navigation.coordinate_system import CoordinateConverter, GridViewportMapper


class NavigationService:
    """Service pour les mouvements simples de navigation dans le jeu."""
    
    def __init__(self, driver, session_service=None):
        """
        Initialise le service de navigation.
        
        Args:
            driver: Instance WebDriver pour interagir avec le jeu
            session_service: Instance SessionSetupService déjà configurée (optionnel)
        """
        self.driver = driver
        self.session_service = session_service
        self.navigation_controller: NavigationController | None = None
        self.coordinate_converter: CoordinateConverter | None = None
        self.viewport_mapper: GridViewportMapper | None = None
        
        # Auto-récupération des composants si session_service disponible
        if session_service:
            self._setup_components()
        else:
            self.coordinate_converter = CoordinateConverter(driver=driver)
            self.viewport_mapper = GridViewportMapper(self.coordinate_converter, driver)
            self.navigation_controller = NavigationController(driver, self.coordinate_converter, self.viewport_mapper)
    
    def _setup_components(self):
        """Configure automatiquement les composants depuis SessionSetupService."""
        try:
            if hasattr(self.session_service, 'get_coordinate_converter'):
                self.coordinate_converter = self.session_service.get_coordinate_converter()
                if self.coordinate_converter:
                    try:
                        self.coordinate_converter.setup_anchor()
                    except Exception as anchor_err:
                        print(f"[NAVIGATION] Impossible d'initialiser l'anchor dès le setup: {anchor_err}")

            if hasattr(self.session_service, 'get_viewport_mapper'):
                self.viewport_mapper = self.session_service.get_viewport_mapper()

            if not self.navigation_controller:
                self.navigation_controller = NavigationController(
                    self.driver,
                    converter=self.coordinate_converter,
                    viewport_mapper=self.viewport_mapper,
                )

            print("[NAVIGATION] Composants de navigation initialisés")

        except Exception as e:
            print(f"[ERREUR] Erreur configuration composants: {e}")
            self.coordinate_converter = self.coordinate_converter or CoordinateConverter(driver=self.driver)
            self.navigation_controller = NavigationController(self.driver, self.coordinate_converter, None)

    def move_viewport(self, dx, dy, wait_after=1.0, log=True):
        """
        Déplace la vue du nombre de pixels spécifié.
        
        Args:
            dx: Déplacement horizontal en pixels (positif = droite, négatif = gauche)
            dy: Déplacement vertical en pixels (positif = bas, négatif = haut)
            wait_after: Temps d'attente après mouvement (secondes)
            log: Afficher les informations de déplacement (bool)
            
        Returns:
            dict: Résultat du mouvement avec succès et détails
        """
        try:
            if not self.navigation_controller:
                return {
                    'success': False,
                    'message': 'Game bot non disponible',
                    'dx': dx,
                    'dy': dy
                }
            
            movement_result = self.navigation_controller.move_viewport(
                dx,
                dy,
                coord_system=self.viewport_mapper,
                wait_after=wait_after,
                log=log,
                scale_factor=2.0
            )
            return movement_result
            
        except Exception as e:
            if log:
                print(f"[ERREUR] Erreur lors du mouvement: {e}")
            return {
                'success': False,
                'message': f'Erreur: {str(e)}',
                'dx': dx,
                'dy': dy
            }

