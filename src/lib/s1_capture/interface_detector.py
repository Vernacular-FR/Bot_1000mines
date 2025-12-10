#!/usr/bin/env python3
"""
Intégration de la détection des positions d'interface dans GameStateExtractor
"""

import os
import sys
import time
from datetime import datetime
import numpy as np

from src.lib.config import PATHS

# Ajouter le répertoire courant au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class InterfaceDetector:
    """Détecteur d'interface pour le masquage intelligent"""
    
    def __init__(self, driver, paths: dict = None):
        self.driver = driver
        self.paths = paths or {}
        self.interface_config = None
        self.window_offset = {"x": 0, "y": 0}  # Pas de décalage pour la fenêtre entière
        
    def detect_interface_positions(self):
        """Détecte les positions des éléments d'interface"""
        print("Detection des positions d'interface pour le masquage...")
        
        try:
            # Éléments à détecter
            elements_to_find = [
                {
                    "name": "escape_link",
                    "selector": "a#escape",
                    "description": "Lien Full screen (vertical 21x95 corrigé)",
                    "width": 21,   # Dimensions corrigées
                    "height": 95   # Dimensions corrigées
                },
                {
                    "name": "status",
                    "selector": "div#status",
                    "description": "Zone de status"
                },
                {
                    "name": "game_controls", 
                    "selector": "div.game-controls",
                    "description": "Contrôles de jeu"
                },
                {
                    "name": "info_button",
                    "selector": "button[aria-label='Info']",
                    "description": "Bouton Info"
                }
            ]
            
            detected_elements = []
            print(f"[INTERFACE] Testing {len(elements_to_find)} selectors...")
            
            for element_info in elements_to_find:
                try:
                    print(f"[INTERFACE] Looking for: {element_info['name']} with selector: {element_info['selector']}")
                    # Trouver l'élément
                    element = self.driver.find_element("css selector", element_info['selector'])
                    
                    # Obtenir sa position et taille
                    location = element.location
                    size = element.size
                    
                    viewport_x = location['x']
                    viewport_y = location['y']
                    
                    # Utiliser les dimensions corrigées pour escape_link
                    if element_info['name'] == 'escape_link':
                        width = element_info['width']   # 21
                        height = element_info['height'] # 95
                    else:
                        width = size['width']
                        height = size['height']
                    
                    # Corriger les coordonnées pour le screenshot
                    screenshot_x = viewport_x
                    screenshot_y = viewport_y - self.window_offset['y']
                    
                    # Déterminer l'orientation
                    orientation = "vertical" if height > width else "horizontal"
                    
                    element_data = {
                        "name": element_info['name'],
                        "selector": element_info['selector'],
                        "description": element_info['description'],
                        "viewport_x": viewport_x,
                        "viewport_y": viewport_y,
                        "screenshot_x": screenshot_x,
                        "screenshot_y": screenshot_y,
                        "width": width,
                        "height": height,
                        "x2": viewport_x + width,
                        "y2": viewport_y + height,
                        "screenshot_x2": screenshot_x + width,
                        "screenshot_y2": screenshot_y + height,
                        "area": width * height,
                        "orientation": orientation
                    }
                    
                    detected_elements.append(element_data)
                    print(f"  [OK] {element_info['name']}: FOUND at ({viewport_x}, {viewport_y}) {width}x{height}")
                    
                except Exception as e:
                    print(f"  [FAIL] {element_info['name']}: NOT FOUND - {str(e)}")
            
            # Créer la configuration
            self.interface_config = {
                "timestamp": datetime.now().isoformat(),
                "window_offset": self.window_offset,
                "elements": detected_elements,
                "total_interface_area": sum(e.get('area', 0) for e in detected_elements),
                "correction_applied": "integrated_detection"
            }
            
            print(f"Détection d'interface terminée: {len(detected_elements)} éléments trouvés")
            
            return self.interface_config
            
        except Exception as e:
            print(f"ERREUR lors de la detection d'interface: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_interface_config(self):
        """Retourne la configuration d'interface"""
        return self.interface_config
    
    def calculate_internal_zone_pixels(self):
        """
        Calcule la zone interne à l'interface en coordonnées pixels.
        
        Returns:
            dict: Zone interne avec left, right, top, bottom en pixels, ou None si erreur
        """
        if not self.interface_config:
            print("[ERREUR] Aucune configuration d'interface disponible")
            return None
        
        elements = {e['name']: e for e in self.interface_config.get('elements', [])}
        required = ['escape_link', 'status', 'game_controls', 'info_button']
        
        if not all(name in elements for name in required):
            print("[ERREUR] Certains éléments d'interface sont manquants")
            return None
        
        escape_el = elements['escape_link']
        status_el = elements['status']
        controls_el = elements['game_controls']
        info_el = elements['info_button']
        
        # Calcul du rectangle interne en coordonnées screenshot
        left = escape_el['screenshot_x2']
        right = status_el['screenshot_x']
        top = controls_el['screenshot_y2']
        bottom = info_el['screenshot_y']
        
        if right <= left or bottom <= top:
            print("[ERREUR] Zone interne invalide (bornes incohérentes)")
            return None
        
        print(f"[INFO] Zone interface interne (pixels): left={left}, right={right}, top={top}, bottom={bottom}")
        
        return {
            'left': left,
            'right': right,
            'top': top,
            'bottom': bottom
        }
    
    def convert_internal_zone_to_grid(self, pixel_zone, coord_system):
        """
        Convertit la zone interne en coordonnées grille en utilisant get_zone_bounds_contained
        pour garantir que toutes les cellules soient entièrement contenues dans la zone.
        
        Args:
            pixel_zone: dict avec left, right, top, bottom en pixels
            coord_system: CoordinateConverter initialisé avec anchor
            
        Returns:
            dict: Zone grille avec start_x, start_y, end_x, end_y, ou None si erreur
        """
        if not pixel_zone or not coord_system:
            print("[ERREUR] Zone pixel ou coord_system manquant")
            return None
        
        try:
            # Utiliser get_zone_bounds_contained pour garantir l'inclusion complète des cellules
            zone_bounds = coord_system.get_zone_bounds_contained(
                pixel_zone['left'], pixel_zone['top'],
                pixel_zone['right'], pixel_zone['bottom']
            )
            
            if not zone_bounds:
                print("[ERREUR] Impossible de calculer les bornes de zone contenue")
                return None
            
            grid_left, grid_top, grid_right, grid_bottom = zone_bounds['grid_bounds']
            
            print(f"[INFO] Zone grille interne (avec get_zone_bounds_contained): ({grid_left}, {grid_top}) -> ({grid_right}, {grid_bottom})")
            
            return {
                'start_x': grid_left,
                'start_y': grid_top,
                'end_x': grid_right,
                'end_y': grid_bottom
            }
            
        except Exception as e:
            print(f"[ERREUR] Erreur conversion zone grille: {e}")
            return None
    
    def create_interface_mask(self, image_shape):
        """Crée un masque pour masquer les éléments d'interface"""
        if not self.interface_config:
            print("AVERTISSEMENT: Aucune configuration d'interface disponible")
            return None
        
        height, width = image_shape[:2]
        mask = np.ones((height, width), dtype=bool)
        
        try:
            # numpy est déjà importé au début du fichier
            for element in self.interface_config['elements']:
                if element.get('screenshot_x') is not None:
                    x1 = element['screenshot_x']
                    y1 = element['screenshot_y']
                    x2 = element['screenshot_x2']
                    y2 = element['screenshot_y2']
                    
                    # Vérifier que les coordonnées sont valides
                    if x1 >= 0 and y1 >= 0 and x2 <= width and y2 <= height:
                        mask[y1:y2, x1:x2] = False  # Masquer l'interface
                        print(f"  Masquage: {element['name']} ({x1}-{x2}, {y1}-{y2})")
            
            return mask
            
        except Exception as e:
            print(f"ERREUR lors de la creation du masque: {str(e)}")
            return None
