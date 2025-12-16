"""
Service de navigation minimal : pure façade sur les controllers `lib/s0_interface`.
Pas de logique d’ancrage ni d’instanciation de composants ici (gérée côté lib).
"""

from src.lib.s0_interface.controller import InterfaceController


class InterfaceService:
    """Façade ultra-légère vers InterfaceController (navigation)."""

    def __init__(self, interface: InterfaceController):
        self.interface = interface
        self.navigation_controller = interface.navigator
        self.viewport_mapper = interface.navigator.viewport_mapper
        self.converter = interface.converter

    def move_viewport(self, dx: float, dy: float, wait_after: float = 1.0, log: bool = True):
        """
        Déplace la vue du nombre de pixels spécifié en s’appuyant sur NavigationController.
        La gestion de l’ancrage/converter/viewport_mapper est du ressort de lib/s0_interface.
        """
        if not self.navigation_controller:
            return {
                "success": False,
                "message": "NavigationController absent",
                "dx": dx,
                "dy": dy,
            }

        try:
            return self.navigation_controller.move_viewport(
                dx,
                dy,
                coord_system=self.viewport_mapper or self.converter,
                wait_after=wait_after,
                log=log,
                scale_factor=2.0,
            )
        except Exception as e:
            if log:
                print(f"[ERREUR] Erreur lors du mouvement: {e}")
            return {
                "success": False,
                "message": f"Erreur: {str(e)}",
                "dx": dx,
                "dy": dy,
            }

