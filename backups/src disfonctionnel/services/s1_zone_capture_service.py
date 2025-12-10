#!/usr/bin/env python3
"""
Service de capture et reconnaissance de grille - version unifiée
Utilise la logique de lib/ pour captures et overlays de grille
"""

from typing import Dict, Any, Optional, Tuple
import os
from datetime import datetime
import numpy as np
from src.lib.s1_capture.screenshot_manager import ScreenshotManager
from src.lib.s1_capture.combined_overlay import CombinedOverlayAssembler
from src.lib.s1_capture.interface_detector import InterfaceDetector
from src.lib.config import PATHS

class ZoneCaptureService:
    """Service de capture de zones et reconnaissance de grille"""
    
    def __init__(self, driver, paths: Dict[str, str], game_id: str = None, session_service=None):
        """
        Initialise le service de capture de zone.
        
        Args:
            driver: Instance WebDriver pour interagir avec le jeu
            paths: Dictionnaire des chemins de sortie
            game_id: Identifiant de partie (optionnel)
            session_service: SessionSetupService pour récupérer les composants (optionnel)
        """
        self.driver = driver
        self.paths = paths
        self.game_id = game_id
        self.session_service = session_service
        
        # Initialiser les composants
        self.screenshot_manager = ScreenshotManager(driver, paths)
        self.interface_detector = InterfaceDetector(driver)
        self.combined_overlay = CombinedOverlayAssembler(paths.get('interface', 'temp/interface'))
        self.enable_combined_overlay = False  # Overlay désactivé par défaut (coûteux)
        
        # Récupérer le coordinate converter si session_service disponible
        self.coordinate_converter = None
        if session_service and hasattr(session_service, 'get_coordinate_converter'):
            try:
                self.coordinate_converter = session_service.get_coordinate_converter()
            except Exception as e:
                print(f"[ZONE_CAPTURE] Impossible de récupérer le coordinate converter: {e}")
        
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Crée les répertoires nécessaires"""
        for path in self.paths.values():
            if not path.endswith('.json') and not path.endswith('.png'):
                os.makedirs(path, exist_ok=True)

    def capture_game_zone_inside_interface(
        self,
        session_service,
        iteration_num: Optional[int] = None,
        limit_grid_bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict[str, Any]:
        """Capture la zone de jeu interne en excluant l'interface."""
        try:
            iteration_info = f" (itération {iteration_num})" if iteration_num is not None else ""
            print(f"[CAPTURE] Capture de la zone de jeu à l'intérieur de l'interface...{iteration_info}")

            interface_config = self.interface_detector.detect_interface_positions()
            if not interface_config:
                return {'success': False, 'error': 'interface_detection_failed', 'message': "Interface non détectée"}

            pixel_zone = self.interface_detector.calculate_internal_zone_pixels()
            if not pixel_zone:
                return {'success': False, 'error': 'pixel_zone_calculation_failed', 'message': "Zone interne en pixels introuvable"}

            coord_system = session_service.get_coordinate_converter()
            viewport_mapper = session_service.get_viewport_mapper()
            grid_zone = self.interface_detector.convert_internal_zone_to_grid(pixel_zone, viewport_mapper or coord_system)
            if not grid_zone:
                return {'success': False, 'error': 'grid_conversion_failed', 'message': "Conversion grid impossible"}

            if limit_grid_bounds:
                limited_zone = self._apply_grid_bounds_limit(grid_zone, limit_grid_bounds)
                if limited_zone:
                    grid_zone = limited_zone
                    pixel_zone = self._grid_bounds_to_pixel_zone(grid_zone, coord_system) or pixel_zone

            zone_path = self.screenshot_manager.capture_between_cells(
                grid_zone['start_x'], grid_zone['start_y'],
                grid_zone['end_x'], grid_zone['end_y'],
                coord_system=coord_system,
                game_id=self.game_id,
                iteration_num=iteration_num
            )

            if not zone_path:
                return {'success': False, 'error': 'capture_failed', 'message': "Capture interne échouée"}

            usable_mask = self._compute_usable_mask(pixel_zone, grid_zone, coord_system)

            return {
                'success': True,
                'zone_path': zone_path,
                'pixel_zone': pixel_zone,
                'grid_zone': grid_zone,
                'usable_mask': usable_mask
            }

        except Exception as e:
            return {'success': False, 'error': str(e), 'message': f"Erreur capture zone interne: {e}"}

    def capture_window(self, filename: str = None) -> Dict[str, Any]:
        """
        Capture la fenêtre entière (capture simple, sans overlay supplémentaire)
        
        Args:
            filename: Nom du fichier (optionnel)
            
        Returns:
            Dict: Résultat de la capture avec chemins des fichiers générés
        """
        try:
            print("[CAPTURE] Capture de la fenêtre entière...")
            capture_result = self.screenshot_manager.capture_viewport(
                filename=filename,
                game_id=self.game_id
            )

            return capture_result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Erreur lors de la capture du viewport: {e}'
            }
    
    def capture_window_with_combined_overlay(self, filename: str = None, overlay_combined: bool = True,
                                           grid_bounds: tuple = (-30, -15, 30, 15), viewport_mapper=None) -> Dict[str, Any]:
        """
        Capture la fenêtre entière avec overlay combiné interface + grille
        
        Args:
            filename: Nom du fichier (optionnel)
            overlay_combined: True pour générer l'overlay combiné, False pour capture simple
            grid_bounds: Limites de la grille pour l'overlay combiné
            viewport_mapper: GridViewportMapper pour la grille
            
        Returns:
            Dict: Résultat de la capture avec chemins des fichiers générés
        """
        try:
            print("[CAPTURE] Capture de la fenêtre avec overlay combiné...")

            capture_result = self.capture_window(filename=filename)
            if not capture_result.get('success'):
                return capture_result

            screenshot_path = capture_result['screenshot_path']

            # Générer l'overlay combiné si demandé
            if overlay_combined and self.enable_combined_overlay:
                print("[COMBINED] Génération de l'overlay combiné interface + grille...")

                # 1. Détecter les positions de l'interface
                interface_config = self.interface_detector.detect_interface_positions()

                if interface_config and isinstance(interface_config, dict) and 'elements' in interface_config:
                    interface_elements = interface_config['elements']
                    print(f"[COMBINED] {len(interface_elements)} éléments d'interface détectés")

                    pixel_zone = self.interface_detector.calculate_internal_zone_pixels()
                    zone_bounds = None
                    if pixel_zone:
                        mapper_or_coord = viewport_mapper or self.coordinate_converter
                        if mapper_or_coord:
                            zone_bounds = self.interface_detector.convert_internal_zone_to_grid(pixel_zone, mapper_or_coord)
                    usable_mask_overlay = None
                    resolved_grid_bounds = grid_bounds
                    if zone_bounds:
                        resolved_grid_bounds = (
                            zone_bounds['start_x'],
                            zone_bounds['start_y'],
                            zone_bounds['end_x'],
                            zone_bounds['end_y'],
                        )
                        if self.coordinate_converter:
                            usable_mask_overlay = self._compute_usable_mask(pixel_zone, zone_bounds, self.coordinate_converter)

                    # 2. Créer l'overlay combiné
                    combined_overlay = self.combined_overlay

                    # Utiliser le game_id dans le nom du fichier si disponible
                    combined_filename = f"{self.game_id}_combined_overlay.png" if self.game_id else f"combined_overlay_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

                    combined_overlay_path = combined_overlay.generate_from_screenshot(
                        screenshot_path,
                        interface_elements,
                        resolved_grid_bounds,
                        coord_system=self.coordinate_converter if hasattr(self, 'coordinate_converter') else None,
                        viewport_mapper=viewport_mapper,
                        filename=combined_filename,
                        usable_mask=usable_mask_overlay
                    )

                    if combined_overlay_path:
                        capture_result['combined_overlay_path'] = combined_overlay_path
                        capture_result['combined_overlay_generated'] = True
                        print(f"[SUCCES] Overlay combiné généré: {combined_overlay_path}")
                    else:
                        capture_result['combined_overlay_generated'] = False
                        print("[ATTENTION] Impossible de générer l'overlay combiné")
                else:
                    capture_result['combined_overlay_generated'] = False
                    print("[ATTENTION] Impossible de détecter l'interface pour l'overlay combiné")

            return capture_result

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Erreur lors de la capture avec overlay combiné: {e}'
            }

    def _compute_usable_mask(self, pixel_zone, grid_zone, coord_system):
        """
        Génère un masque booléen indiquant les cellules entièrement contenues dans la zone capturée.
        """
        if not pixel_zone or not grid_zone or not coord_system:
            return None

        start_x = grid_zone['start_x']
        start_y = grid_zone['start_y']
        end_x = grid_zone['end_x']
        end_y = grid_zone['end_y']

        width = end_x - start_x + 1
        height = end_y - start_y + 1

        mask = np.zeros((height, width), dtype=bool)

        left = pixel_zone['left']
        top = pixel_zone['top']
        right = pixel_zone['right']
        bottom = pixel_zone['bottom']

        cell_total = coord_system.cell_total if hasattr(coord_system, "cell_total") else coord_system.cell_size

        for gy in range(height):
            grid_y = start_y + gy
            for gx in range(width):
                grid_x = start_x + gx
                cell_left, cell_top = coord_system.grid_to_screen(grid_x, grid_y)
                cell_right = cell_left + cell_total
                cell_bottom = cell_top + cell_total

                if (cell_left >= left and cell_top >= top and
                        cell_right <= right and cell_bottom <= bottom):
                    mask[gy, gx] = True

        return mask

    def _apply_grid_bounds_limit(
        self,
        base_zone: Dict[str, int],
        limit_bounds: Tuple[int, int, int, int],
    ) -> Optional[Dict[str, int]]:
        limited = {
            'start_x': max(base_zone['start_x'], limit_bounds[0]),
            'start_y': max(base_zone['start_y'], limit_bounds[1]),
            'end_x': min(base_zone['end_x'], limit_bounds[2]),
            'end_y': min(base_zone['end_y'], limit_bounds[3]),
        }
        if limited['start_x'] > limited['end_x'] or limited['start_y'] > limited['end_y']:
            return None
        return limited

    def _grid_bounds_to_pixel_zone(
        self,
        grid_zone: Dict[str, int],
        coord_system,
    ) -> Optional[Dict[str, int]]:
        if not coord_system:
            return None
        try:
            cell_left, cell_top = coord_system.grid_to_screen(grid_zone['start_x'], grid_zone['start_y'])
            cell_right, cell_bottom = coord_system.grid_to_screen(grid_zone['end_x'] + 1, grid_zone['end_y'] + 1)
            return {
                'left': int(cell_left),
                'top': int(cell_top),
                'right': int(cell_right),
                'bottom': int(cell_bottom),
            }
        except Exception as exc:
            print(f"[ZONE_CAPTURE] Impossible de convertir les bornes limitées en pixels: {exc}")
            return None
