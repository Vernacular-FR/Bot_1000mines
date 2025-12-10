from __future__ import annotations

import math
from typing import List, Tuple, Optional, Dict

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .s03_Coordonate_system import CoordinateConverter


class ViewportMapper:
    """
    Lecture des limites du viewport (#control) et des zones visibles pour la capture.
    """

    def __init__(self, converter: CoordinateConverter, driver=None):
        """
        Args:
            converter: convertisseur grille/canvas/écran partagé avec s0.
            driver: WebDriver utilisé pour lire #control.
        """
        self.converter = converter
        self.driver = driver
        self.control_element = None

    def set_driver(self, driver):
        self.driver = driver
        self.control_element = None

    def get_control_element(self):
        """
        Récupère l'élément #control (viewport graphique).
        """
        if not self.driver:
            raise RuntimeError("Le WebDriver n'est pas défini pour ViewportMapper")

        if not self.control_element:
            self.control_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "control"))
            )
        return self.control_element

    # ------------------------------------------------------------------
    # Helpers limites grille/écran
    # ------------------------------------------------------------------

    def get_grid_bounds(self, grid_coords_list: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
        if not grid_coords_list:
            return (0, 0, 0, 0)

        x_coords = [coord[0] for coord in grid_coords_list]
        y_coords = [coord[1] for coord in grid_coords_list]
        return min(x_coords), min(y_coords), max(x_coords), max(y_coords)

    def get_screen_bounds(self, grid_coords_list: List[Tuple[int, int]]) -> Tuple[float, float, float, float]:
        min_x, min_y, max_x, max_y = self.get_grid_bounds(grid_coords_list)
        top_left = self.converter.grid_to_screen(min_x, min_y)
        bottom_right = self.converter.grid_to_screen(max_x + 1, max_y + 1)
        return top_left[0], top_left[1], bottom_right[0], bottom_right[1]

    def get_zone_bounds_contained(self, left_screen, top_screen, right_screen, bottom_screen) -> Optional[Dict]:
        """
        Fournit les bornes grille/écran d'une zone entièrement contenue.
        """
        try:
            grid_left, grid_top = self.converter.screen_to_grid(left_screen, top_screen)
            grid_right, grid_bottom = self.converter.screen_to_grid(right_screen, bottom_screen)

            grid_left = math.ceil(grid_left)
            grid_top = math.ceil(grid_top)
            grid_right = math.floor(grid_right) - 1
            grid_bottom = math.floor(grid_bottom) - 1

            return {
                "grid_bounds": (grid_left, grid_top, grid_right, grid_bottom),
                "screen_bounds": (left_screen, top_screen, right_screen, bottom_screen),
            }
        except Exception as e:
            print(f"[ERREUR] Erreur lors du calcul des bornes de zone contenue: {e}")
            return None

    # ------------------------------------------------------------------
    # Viewport readings
    # ------------------------------------------------------------------

    def get_viewport_bounds(self):
        """
        Retourne les limites du viewport en pixels + indices grille visibles.
        """
        if not self.driver:
            raise RuntimeError("Driver requis pour mesurer le viewport")

        from src.config import VIEWPORT_CONFIG

        control_element = self.get_control_element()
        viewport_width = control_element.rect["width"]
        viewport_height = control_element.rect["height"]
        viewport_left, viewport_top = VIEWPORT_CONFIG["position"]

        left = viewport_left
        top = viewport_top
        right = viewport_left + viewport_width
        bottom = viewport_top + viewport_height

        zone_bounds = self.get_zone_bounds_contained(left, top, right, bottom)
        if not zone_bounds:
            return None

        grid_left, grid_top, grid_right, grid_bottom = zone_bounds["grid_bounds"]
        return {
            "screen_bounds": (left, top, right, bottom),
            "grid_bounds": (grid_left, grid_top, grid_right, grid_bottom),
            "dimensions": (viewport_width, viewport_height),
            "position": VIEWPORT_CONFIG["position"],
        }

    def get_viewport_corners(self):
        """
        Coordonnées des 4 coins du viewport en grille + log debug.
        """
        try:
            viewport_info = self.get_viewport_bounds()
            if not viewport_info:
                return {}

            grid_left, grid_top, grid_right, grid_bottom = viewport_info["grid_bounds"]
            corners = {
                "top_left": (grid_left, grid_top),
                "top_right": (grid_right, grid_top),
                "bottom_left": (grid_left, grid_bottom),
                "bottom_right": (grid_right, grid_bottom),
            }

            print("[INFO] Coordonnées des coins du viewport:")
            for corner, (x, y) in corners.items():
                screen_x, screen_y = self.converter.grid_to_screen(x, y)
                print(f"   {corner}: grille({x:.1f}, {y:.1f}) -> écran({screen_x:.0f}, {screen_y:.0f})")

            return corners
        except Exception as e:
            print(f"[ERREUR] Erreur lors du calcul des coins du viewport: {e}")
            return {}

    def get_grid_bounds(self, grid_coords_list):
        """
        Calcule les limites d'une zone de grille.
        
        Args:
            grid_coords_list: Liste de tuples (x, y) de coordonnées de grille
            
        Returns:
            tuple: (min_x, min_y, max_x, max_y) limites de la zone
        """
        # Vérifier si la liste est vide
        if not grid_coords_list:
            return (0, 0, 0, 0)
        
        # Extraire les coordonnées X et Y de chaque tuple
        x_coords = [coord[0] for coord in grid_coords_list]
        y_coords = [coord[1] for coord in grid_coords_list]
        
        # Calculer les limites de la zone
        min_x = min(x_coords)
        min_y = min(y_coords)
        max_x = max(x_coords)
        max_y = max(y_coords)
        
        return (min_x, min_y, max_x, max_y)

    def get_screen_bounds(self, grid_coords_list):
        """
        Calcule les limites d'une zone en coordonnées écran.
        
        Args:
            grid_coords_list: Liste de tuples (x, y) de coordonnées de grille
            
        Returns:
            tuple: (left, top, right, bottom) limites en pixels
        """
        # Obtenir les limites de grille
        min_x, min_y, max_x, max_y = self.get_grid_bounds(grid_coords_list)
        
        # Convertir les limites de grille en coordonnées écran
        top_left = self.converter.grid_to_screen(min_x, min_y)
        bottom_right = self.converter.grid_to_screen(max_x + 1, max_y + 1)
        
        return top_left[0], top_left[1], bottom_right[0], bottom_right[1]

    def get_zone_bounds_contained(self, left_screen, top_screen, right_screen, bottom_screen):
        """
        Calcule les bornes d'une zone en coordonnées grille en garantissant que
        toutes les cellules soient entièrement contenues dans la zone.
        
        Utilise la même logique que get_viewport_bounds mais pour une zone arbitraire.
        
        Args:
            left_screen: Coordonnée X gauche de la zone en pixels écran
            top_screen: Coordonnée Y supérieure de la zone en pixels écran
            right_screen: Coordonnée X droite de la zone en pixels écran
            bottom_screen: Coordonnée Y inférieure de la zone en pixels écran
            
        Returns:
            dict: Bornes de la zone contenue {
                'grid_bounds': (grid_left, grid_top, grid_right, grid_bottom),
                'screen_bounds': (left, top, right, bottom)
            }
        """
        try:
            # Convertir les coins en coordonnées grille
            grid_left, grid_top = self.converter.screen_to_grid(left_screen, top_screen)
            grid_right, grid_bottom = self.converter.screen_to_grid(right_screen, bottom_screen)
            
            # Pour les cellules entièrement contenues dans la zone :
            # ceil pour les bornes inférieures, floor pour les bornes supérieures
            import math
            grid_left = math.ceil(grid_left)        # Première cellule entièrement à l'intérieur
            grid_top = math.ceil(grid_top)          # Première cellule entièrement à l'intérieur
            grid_right = math.floor(grid_right) - 1    # Dernière cellule entièrement à l'intérieur
            grid_bottom = math.floor(grid_bottom) - 1  # Dernière cellule entièrement à l'intérieur
            
            return {
                'grid_bounds': (grid_left, grid_top, grid_right, grid_bottom),
                'screen_bounds': (left_screen, top_screen, right_screen, bottom_screen)
            }
            
        except Exception as e:
            print(f"[ERREUR] Erreur lors du calcul des bornes de zone contenue: {e}")
            return None

    def get_viewport_bounds(self):
        """
        Calcule les bornes x et y du viewport dans le grid space.
        
        Le viewport est positionné avec son coin supérieur gauche aux coordonnées écran (0, 54).
        Retourne les indices des colonnes et lignes contenues dans le viewport.
        
        Returns:
            dict: Bornes du viewport {
                'screen_bounds': (left, top, right, bottom),  # Limites en pixels écran
                'grid_bounds': (grid_left, grid_top, grid_right, grid_bottom),  # Colonnes/lignes dans le viewport
                'dimensions': (width, height),  # Dimensions en pixels
                'position': (0, 54)  # Position du coin supérieur gauche en pixels
            }
        """
        try:
            from src.config import VIEWPORT_CONFIG
            
            # Récupérer les dimensions du viewport depuis l'élément #control
            control_element = self.get_control_element()
            viewport_width = control_element.rect['width']
            viewport_height = control_element.rect['height']
            
            # Position du viewport depuis la configuration
            viewport_left, viewport_top = VIEWPORT_CONFIG['position']
            
            # Calculer les limites en coordonnées écran
            left = viewport_left
            top = viewport_top
            right = viewport_left + viewport_width
            bottom = viewport_top + viewport_height
            
            # Utiliser get_zone_bounds_contained pour calculer les bornes grille
            zone_bounds = self.get_zone_bounds_contained(left, top, right, bottom)
            if not zone_bounds:
                return None
            
            grid_left, grid_top, grid_right, grid_bottom = zone_bounds['grid_bounds']
            
            return {
                'screen_bounds': (left, top, right, bottom),
                'grid_bounds': (grid_left, grid_top, grid_right, grid_bottom),
                'dimensions': (viewport_width, viewport_height),
                'position': VIEWPORT_CONFIG['position']
            }
            
        except Exception as e:
            print(f"[ERREUR] Erreur lors du calcul des bornes du viewport: {e}")
            return None

    def get_viewport_corners(self):
        """
        Calcule les coordonnées des 4 angles du viewport actuel
        en utilisant get_viewport_bounds().
        
        Returns:
            dict: Dictionnaire avec les coordonnées des 4 coins en grille
        """
        try:
            viewport_info = self.get_viewport_bounds()
            if not viewport_info:
                return {}
            
            grid_bounds = viewport_info['grid_bounds']
            grid_left, grid_top, grid_right, grid_bottom = grid_bounds
            
            # Déterminer les coins du viewport en coordonnées grille
            corners = {
                'top_left': (grid_left, grid_top),
                'top_right': (grid_right, grid_top), 
                'bottom_left': (grid_left, grid_bottom),
                'bottom_right': (grid_right, grid_bottom)
            }
            
            print("[INFO] Coordonnées des coins du viewport (calculées automatiquement):")
            for corner, (x, y) in corners.items():
                screen_x, screen_y = self.converter.grid_to_screen(x, y)
                print(f"   {corner}: grille({x:.1f}, {y:.1f}) -> écran({screen_x:.0f}, {screen_y:.0f})")
            
            print(f"[INFO] Bounds grille: ({grid_left:.1f}, {grid_top:.1f}) -> ({grid_right:.1f}, {grid_bottom:.1f})")
            print(f"[INFO] Bounds écran: {viewport_info['screen_bounds']}")
            print(f"[INFO] Dimensions viewport: {viewport_info['dimensions']}")
            
            return corners
            
        except Exception as e:
            print(f"[ERREUR] Erreur lors du calcul des coins du viewport: {e}")
            return {}