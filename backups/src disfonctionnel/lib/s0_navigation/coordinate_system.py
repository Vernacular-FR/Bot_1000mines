import math
import sys
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.lib.config import CELL_SIZE, CELL_BORDER, GRID_REFERENCE_POINT

# Import du système de logging centralisé
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Logs.logger import save_bot_log

"""Coordinate system utilities providing conversion + viewport inspection tools."""

# ---------------------------------------------------------------------------
# Coordinate conversion core
# ---------------------------------------------------------------------------


class CoordinateConverter:
    """Gère les conversions entre Canvas/Screen/Grid pour l'ancrage du jeu."""
    
    def __init__(self, cell_size=CELL_SIZE, cell_border=CELL_BORDER, anchor_element=None, driver=None):
        """
        Initialise le convertisseur de coordonnées avec les paramètres graphiques du jeu.
        """
        self.cell_size = cell_size # Taille d'une case en pixels 
        self.cell_border = cell_border # Épaisseur des bordures entre les cases en pixels 
        self.cell_total = cell_size + cell_border # 25px par défaut
        self.cell_center_offset = math.ceil(self.cell_total / 2.0) # Centre de la cellule (13px : laisse 12px de chaque côté de la cellule de 25x25px)
        self.anchor = anchor_element # Élément #anchor du jeu : origine du CanvasSpace
        self.driver = driver # Instance du WebDriver pour détecter les éléments de la page
        self.grid_reference_point = GRID_REFERENCE_POINT

    def setup_anchor(self):
        """
        Configure l'élément anchor comme référence pour les conversions de coordonnées.
        L'anchor est l'élément DOM qui sert de point de référence pour les coordonnées Canvas.
        """
        if not self.driver:
            raise RuntimeError("Driver non initialisé. Utilisez set_driver() d'abord.")
            
        try:
            # Récupérer l'élément anchor (#anchor)
            self.anchor = self.driver.find_element("css selector", "#anchor")
            print(f"[INFO] Anchor configuré avec succès: {self.anchor}")
        except Exception as e:
            raise RuntimeError(f"Impossible de trouver l'élément anchor: {e}")

    def get_anchor_css_position(self):
        """
        Récupère la position CSS réelle de l'anchor (coordonnées viewport).
        """
        if not self.anchor:
            raise RuntimeError("Anchor non configuré")
            
        # Exécuter du JavaScript pour obtenir les coordonnées CSS
        script = """
        var element = arguments[0];
        var style = window.getComputedStyle(element);
        var rect = element.getBoundingClientRect();
        return {
            x: rect.left,
            y: rect.top,
            css_left: style.left,
            css_top: style.top,
            element_left: element.style.left,
            element_top: element.style.top
        };
        """
        
        result = self.driver.execute_script(script, self.anchor)
        
        return result

    def refresh_anchor(self):
        """
        Rafraîchit la position de l'anchor avant conversion.
        Met à jour les coordonnées de référence pour garantir la précision.
        """
        if self.anchor:
            self.setup_anchor()
            print("[DEBUG] Anchor rafraîchi")
        
    def canvas_to_screen(self, canvas_x, canvas_y):
        """
        Convertit les coordonnées Canvas en coordonnées écran (pixels absolus).
        
        Args:
            canvas_x: Coordonnée X dans le CanvasSpace
            canvas_y: Coordonnée Y dans le CanvasSpace
            
        Returns:
            tuple: (screen_x, screen_y) coordonnées absolues en pixels
        """
        if not self.anchor:
            raise RuntimeError("L'élément anchor n'est pas défini. Utilisez setup_anchor() d'abord.")
            
        # Utiliser les coordonnées CSS réelles (viewport) au lieu de Selenium
        anchor_pos = self.get_anchor_css_position()
        anchor_x = anchor_pos['x']
        anchor_y = anchor_pos['y']
        
        # Calculer les coordonnées écran
        screen_x = anchor_x + canvas_x
        screen_y = anchor_y + canvas_y
        
        return screen_x, screen_y

    def screen_to_canvas(self, screen_x, screen_y):
        """
        Convertit les coordonnées écran en coordonnées Canvas.
        
        Args:
            screen_x: Coordonnée X absolue en pixels
            screen_y: Coordonnée Y absolue en pixels
            
        Returns:
            tuple: (canvas_x, canvas_y) coordonnées dans le CanvasSpace
        """
        if not self.anchor:
            raise RuntimeError("L'élément anchor n'est pas défini. Utilisez setup_anchor() d'abord.")
            
        # Utiliser les coordonnées CSS réelles (viewport) au lieu de Selenium
        anchor_pos = self.get_anchor_css_position()
        anchor_x = anchor_pos['x']
        anchor_y = anchor_pos['y']
        
        # Calculer les coordonnées canvas
        canvas_x = screen_x - anchor_x
        canvas_y = screen_y - anchor_y
        
        return canvas_x, canvas_y

    def canvas_to_grid(self, canvas_x, canvas_y):
        """
        Convertit les coordonnées Canvas en coordonnées de grille.
        
        Args:
            canvas_x: Coordonnée X dans le CanvasSpace
            canvas_y: Coordonnée Y dans le CanvasSpace
            
        Returns:
            tuple: (grid_x, grid_y) coordonnées de grille
        """
        grid_x = canvas_x / self.cell_total
        grid_y = canvas_y / self.cell_total
        
        return grid_x, grid_y

    def grid_to_canvas(self, grid_x, grid_y):
        """
        Convertit les coordonnées de grille en coordonnées Canvas.
        
        Args:
            grid_x: Coordonnée X dans la grille
            grid_y: Coordonnée Y dans la grille
            
        Returns:
            tuple: (canvas_x, canvas_y) coordonnées dans le CanvasSpace
        """
        canvas_x = grid_x * self.cell_total
        canvas_y = grid_y * self.cell_total
        
        return canvas_x, canvas_y

    def screen_to_grid(self, screen_x, screen_y):
        """
        Convertit les coordonnées écran en coordonnées de grille.
        
        Args:
            screen_x: Coordonnée X absolue en pixels
            screen_y: Coordonnée Y absolue en pixels
            
        Returns:
            tuple: (grid_x, grid_y) coordonnées de grille
        """
        # Convertir d'abord en coordonnées canvas
        canvas_x, canvas_y = self.screen_to_canvas(screen_x, screen_y)
        
        # Puis convertir en coordonnées de grille
        grid_x, grid_y = self.canvas_to_grid(canvas_x, canvas_y)
        
        return grid_x, grid_y

    def grid_to_screen(self, grid_x, grid_y):
        """
        Convertit les coordonnées de grille en coordonnées écran.
        
        Args:
            grid_x: Coordonnée X dans la grille
            grid_y: Coordonnée Y dans la grille
            
        Returns:
            tuple: (screen_x, screen_y) coordonnées absolues en pixels
        """
        # Convertir d'abord en coordonnées canvas
        canvas_x, canvas_y = self.grid_to_canvas(grid_x, grid_y)
        
        # Puis convertir en coordonnées écran
        screen_x, screen_y = self.canvas_to_screen(canvas_x, canvas_y)
        
        return screen_x, screen_y

    def grid_to_screen_centered(self, grid_x, grid_y):
        """
        Calcule les coordonnées écran du centre d'une cellule de grille.
        
        Args:
            grid_x: Coordonnée X dans la grille
            grid_y: Coordonnée Y dans la grille
            
        Returns:
            tuple: (center_x, center_y) coordonnées du centre en pixels
        """
        # Convertir les coordonnées de grille en coordonnées écran
        screen_x, screen_y = self.grid_to_screen(grid_x, grid_y)
        
        # Ajouter le décalage pour atteindre le centre de la cellule
        center_x = screen_x + self.cell_center_offset
        center_y = screen_y + self.cell_center_offset
        
        return center_x, center_y


class GridViewportMapper:
    """
    Gère l'inspection des limites et du viewport pour la grille du jeu.
    """
    
    def __init__(self, converter: CoordinateConverter, driver=None):
        """
        Initialise l'inspecteur de limites avec un convertisseur de coordonnées.
        
        Args:
            converter: Instance de CoordinateConverter pour les conversions
            driver: Instance du WebDriver pour détecter les éléments de la page
        """
        self.converter = converter
        self.driver = driver
        self.control_element = None
        
    def get_control_element(self):
        """
        Récupère l'élément #control de la page (viewport)
        """
        if not self.driver:
            raise RuntimeError("Le WebDriver n'est pas défini dans le système de coordonnées")
            
        if not self.control_element:
            self.control_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "control"))
            )
        return self.control_element

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
            from src.lib.config import VIEWPORT_CONFIG
            
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