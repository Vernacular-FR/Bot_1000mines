import math
import os
import re
import sys
from typing import Dict, List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.lib.config import CELL_SIZE, CELL_BORDER, GRID_REFERENCE_POINT

# Import du système de logging centralisé
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Logs.logger import save_bot_log

"""Utilities for viewport geometry: canvas localisation, coordinate conversions, viewport mapping."""




class CoordinateConverter:
    """Gère les conversions entre Canvas/Screen/Grid et localise les canvas."""

    def __init__(
        self,
        cell_size=CELL_SIZE,
        cell_border=CELL_BORDER,
        anchor_element=None,
        driver=None,
        canvas_locator: CanvasLocator | None = None,
    ):
        """
        Initialise le convertisseur de coordonnées avec les paramètres graphiques du jeu.
        """
        self.cell_size = cell_size # Taille d'une case en pixels 
        self.cell_border = cell_border # Épaisseur des bordures entre les cases en pixels 
        self.cell_total = cell_size + cell_border # 25px par défaut
        self.cell_center_offset = math.ceil(self.cell_total / 2.0) # Centre de la cellule (13px : laisse 12px de chaque côté de la cellule de 25x25px)
        self.anchor = anchor_element # Élément #anchor du jeu : origine du CanvasSpace
        self.driver = driver # Instance du WebDriver pour détecter les éléments de la page
        self.canvas_locator = canvas_locator or CanvasLocator(driver)
        self.grid_reference_point = GRID_REFERENCE_POINT

    def set_driver(self, driver):
        self.driver = driver
        self.canvas_locator.set_driver(driver)
        self.anchor = None

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

    def locate_canvas(self, canvas_id: str):
        """
        Fournit les offsets écran/relatifs pour un canvas donné (ex. canvas_space).
        """
        if not self.canvas_locator:
            raise RuntimeError("CanvasLocator non défini sur CoordinateConverter")
        return self.canvas_locator.locate(canvas_id)

class CanvasLocator:
    """Localise les canvases (512×512) autour de #anchor et renvoie offsets absolus/relatifs."""

    TILE_ID_PATTERN = re.compile(r"(?P<x>-?\d+)x(?P<y>-?\d+)")

    def __init__(self, driver=None, anchor_selector="#anchor", canvas_selector="canvas"):
        self.driver = driver
        self.anchor_selector = anchor_selector
        self.canvas_selector = canvas_selector
        self._anchor_element = None
        self._anchor_rect_cache = None
        self._descriptors_cache: Optional[List[Dict]] = None

    def set_driver(self, driver):
        self.driver = driver
        self._anchor_element = None
        self._anchor_rect_cache = None
        self._descriptors_cache = None

    # ------------------------------
    # Helpers
    # ------------------------------

    def _require_driver(self):
        if not self.driver:
            raise RuntimeError("Driver non initialisé pour CanvasLocator")

    def _get_anchor_element(self):
        self._require_driver()
        if not self._anchor_element:
            self._anchor_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.anchor_selector))
            )
        return self._anchor_element

    def _get_anchor_rect(self):
        if self._anchor_rect_cache is None:
            self._anchor_rect_cache = self._element_rect(self._get_anchor_element())
        return self._anchor_rect_cache

    def _element_rect(self, element):
        script = """
        const el = arguments[0];
        const rect = el.getBoundingClientRect();
        return {
            left: rect.left,
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
            width: rect.width,
            height: rect.height
        };
        """
        return self.driver.execute_script(script, element)

    def _parse_tile_id(self, canvas_id):
        match = self.TILE_ID_PATTERN.match(canvas_id)
        if not match:
            return None, None
        return int(match.group("x")), int(match.group("y"))

    # ------------------------------
    # Public API
    # ------------------------------

    def locate(self, canvas_id):
        """
        Mesure la position d'un canvas en pixels absolus et relatifs à #anchor.
        """
        self._require_driver()
        canvas = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, canvas_id))
        )
        return self._build_descriptor(canvas)

    def locate_all(self):
        """
        Retourne/cached la liste de tous les canvas présents sous #anchor.
        """
        self._require_driver()
        if self._descriptors_cache is None:
            anchor_rect = self._get_anchor_rect()
            canvases = self.driver.find_elements(By.CSS_SELECTOR, f"{self.anchor_selector} {self.canvas_selector}")
            self._descriptors_cache = [
                self._build_descriptor(canvas, anchor_rect) for canvas in canvases
            ]
        return self._descriptors_cache

    def find_canvas_for_point(self, relative_x: float, relative_y: float) -> Optional[Dict]:
        """
        Retourne le canvas qui recouvre une coordonnée donnée dans le CanvasSpace (#anchor).
        """
        for descriptor in self.locate_all():
            if (
                descriptor["relative_left"] <= relative_x < descriptor["relative_left"] + descriptor["width"]
                and descriptor["relative_top"] <= relative_y < descriptor["relative_top"] + descriptor["height"]
            ):
                return descriptor
        return None

    def _build_descriptor(self, canvas_element, anchor_rect=None):
        if anchor_rect is None:
            anchor_rect = self._get_anchor_rect()
        canvas_rect = self._element_rect(canvas_element)
        canvas_id = canvas_element.get_attribute("id") or "unknown"
        tile_x, tile_y = self._parse_tile_id(canvas_id)

        return {
            "id": canvas_id,
            "tile": (tile_x, tile_y),
            "screen_left": canvas_rect["left"],
            "screen_top": canvas_rect["top"],
            "width": canvas_rect["width"],
            "height": canvas_rect["height"],
            "relative_left": canvas_rect["left"] - anchor_rect["left"],
            "relative_top": canvas_rect["top"] - anchor_rect["top"],
        }

