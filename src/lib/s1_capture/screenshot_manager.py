import os
from datetime import datetime
from typing import Dict, Any, Optional

from PIL import Image
from selenium import webdriver

from src.lib.config import PATHS


class ScreenshotManager:
    """Gestionnaire de captures d'écran simplifié"""

    def __init__(self, driver: webdriver.Chrome, paths: Dict[str, str] = None):
        """Initialise le gestionnaire de captures."""
        self.driver = driver
        self.paths = paths or PATHS
        self._ensure_directories()

    def _ensure_directories(self):
        for path in self.paths.values():
            if not path.endswith('.json'):
                os.makedirs(path, exist_ok=True)

    def capture_viewport(self, filename: str = None, game_id: str = None, iteration_num: int = None) -> Dict[str, Any]:
        try:
            resolved_filename = self._resolve_viewport_filename(filename, game_id, iteration_num)
            viewport_dir = self._resolve_viewport_directory()
            filepath = os.path.join(viewport_dir, resolved_filename)
            self.driver.save_screenshot(filepath)

            return {
                'success': True,
                'screenshot_path': filepath,
                'message': 'Viewport capturé avec succès'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Erreur lors de la capture du viewport: {e}'
            }

    def capture_between_cells(self,
                              cell1_x: int,
                              cell1_y: int,
                              cell2_x: int,
                              cell2_y: int,
                              filename: str = None,
                              add_margin: bool = False,
                              coord_system=None,
                              game_id: str = None,
                              iteration_num: int = None) -> Optional[str]:
        try:
            coord_system = self._ensure_coord_system(coord_system)
            x_min, y_min, x_max, y_max = self._grid_bounds_to_pixels(
                coord_system,
                cell1_x,
                cell1_y,
                cell2_x,
                cell2_y,
                add_margin,
            )

            viewport_filename = self._resolve_viewport_filename(None, game_id, iteration_num)
            full_page_result = self.capture_viewport(
                filename=viewport_filename,
                game_id=game_id,
                iteration_num=iteration_num
            )
            if not full_page_result['success']:
                return None

            full_page_path = full_page_result['screenshot_path']

            with Image.open(full_page_path) as img:
                zone_img = img.crop((x_min, y_min, x_max, y_max))

                resolved_zone_name = filename or self._build_zone_filename(game_id, cell1_x, cell1_y, cell2_x, cell2_y, iteration_num)
                zone_path = os.path.join(self.paths.get('zone', 'temp/zones'), resolved_zone_name)
                zone_img.save(zone_path)

            return zone_path

        except Exception as e:
            print(f"[ERREUR] Erreur lors de la capture entre cases: {e}")
            return None

    def _resolve_viewport_filename(self, filename, game_id, iteration_num):
        if filename is not None:
            return filename
        if game_id is not None and iteration_num is not None:
            return f"{game_id}_iter{iteration_num}_viewport.png"
        if game_id is not None:
            return f"{game_id}_viewport.png"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"viewport_{timestamp}.png"

    def _resolve_viewport_directory(self):
        if 'full_pages' in self.paths:
            return self.paths['full_pages']
        if 'full_page_screenshots' in self.paths:
            return self.paths['full_page_screenshots']
        return list(self.paths.values())[0]

    def _ensure_coord_system(self, coord_system):
        if coord_system is not None:
            return coord_system
        from .coordinate_system import CoordinateConverter
        coord_system = CoordinateConverter(driver=self.driver)
        coord_system.setup_anchor()
        return coord_system

    def _grid_bounds_to_pixels(self, coord_system, cell1_x, cell1_y, cell2_x, cell2_y, add_margin):
        px1, py1 = coord_system.grid_to_screen(cell1_x, cell1_y)
        px2, py2 = coord_system.grid_to_screen(cell2_x, cell2_y)
        x_min = min(px1, px2)
        y_min = min(py1, py2)
        x_max = max(px1, px2)
        y_max = max(py1, py2)
        if add_margin:
            cell_size = coord_system.cell_size
            x_min -= cell_size
            y_min -= cell_size
            x_max += cell_size
            y_max += cell_size
        return x_min, y_min, x_max, y_max

    def _build_zone_filename(self, game_id, cell1_x, cell1_y, cell2_x, cell2_y, iteration_num=None):
        final_game_id = game_id or self._infer_game_id_from_paths() or "unknown"
        if iteration_num is not None:
            return f"{final_game_id}_iter{iteration_num}_zone_{cell1_x}_{cell1_y}_{cell2_x}_{cell2_y}.png"
        return f"{final_game_id}_zone_{cell1_x}_{cell1_y}_{cell2_x}_{cell2_y}.png"

    def _infer_game_id_from_paths(self):
        zone_dir = self.paths.get('zone')
        if not zone_dir:
            return None
        path_parts = zone_dir.split(os.sep)
        if 'games' in path_parts:
            idx = path_parts.index('games')
            if idx + 1 < len(path_parts):
                return path_parts[idx + 1]
        return None
