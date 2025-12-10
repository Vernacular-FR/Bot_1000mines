import time
import sys
import os
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from src.lib.config import CELL_SIZE, CELL_BORDER, WAIT_TIMES
from .viewport_geometry import CoordinateConverter, ViewportMapper

# Import du système de logging centralisé
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Logs.logger import save_bot_log

class GameSessionController:
    """Responsable de la sélection du mode de jeu et de l'initialisation du plateau."""

    def __init__(self, driver):
        self.driver = driver
        self.game_board = None
        self.converter: Optional[CoordinateConverter] = None
        self.viewport_mapper: Optional[GridViewportMapper] = None
        self.anchor = None

    @staticmethod
    def get_difficulty_from_user():
        from src.lib.config import DIFFICULTY_CONFIG, DEFAULT_DIFFICULTY

        print("\nChoisissez la difficulté :")
        difficulty_list = list(DIFFICULTY_CONFIG.keys())

        for i, difficulty in enumerate(difficulty_list, 1):
            config = DIFFICULTY_CONFIG[difficulty]
            print(f"{i}. {config['name']}")

        choice = input(f"Votre choix (1-{len(difficulty_list)}, défaut: {DEFAULT_DIFFICULTY}): ").strip()

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(difficulty_list):
                return difficulty_list[choice_num - 1]
        except ValueError:
            pass

        return DEFAULT_DIFFICULTY

    def select_game_mode(self, difficulty=None):
        selected_difficulty = difficulty or self.get_difficulty_from_user()

        try:
            print(f"\nSélection du mode de jeu: {selected_difficulty}")
            self._wait_for_mode_controls()
            self._click_infinite_mode()
            config = self._resolve_difficulty_config(selected_difficulty)
            self._select_difficulty_button(config)
            self._initialize_board_and_coords()
            return True

        except Exception as e:
            print(f"\nERREUR: Erreur lors de la sélection du mode de jeu: {e}")
            import traceback
            traceback.print_exc()
            return False


    # Helpers pour la sélection du mode de jeu et la configuration

    def _wait_for_mode_controls(self):
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/#infinite']"))
        )

    def _click_infinite_mode(self):
        infinite_button = self.driver.find_element(By.CSS_SELECTOR, "a[href='/#infinite'] button")
        infinite_button.click()
        print("   - Mode Infinite sélectionné")
        time.sleep(1)

    def _resolve_difficulty_config(self, difficulty_name: str):
        from src.lib.config import DIFFICULTY_CONFIG

        config = DIFFICULTY_CONFIG.get(difficulty_name.lower())
        if not config:
            config = DIFFICULTY_CONFIG['impossible']
        return config

    def _select_difficulty_button(self, difficulty_config):
        difficulty_id = difficulty_config['selenium_id']
        try:
            element = self.driver.execute_script(f"return document.querySelector('#{difficulty_id}');")
            if element:
                self.driver.execute_script(f"document.querySelector('#{difficulty_id}').click();")
                print(f"   - Difficulté {difficulty_config['name']} sélectionnée")
            else:
                print(f"   - Élément #{difficulty_id} non trouvé, tentative alternative...")
                self.driver.execute_script('document.querySelector("[id=\\"new-game\\"]").click();')
                print("   - Difficulté sélectionnée via méthode alternative")
        except Exception as e:
            print(f"   - Erreur lors de la sélection: {e}")

    def _initialize_board_and_coords(self):
        self.game_board = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#control"))
        )
        print("   - Plateau de jeu détecté")
        self.anchor = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#anchor"))
        )
        print("   - Élément anchor détecté")
        self.converter = CoordinateConverter(cell_size=CELL_SIZE, cell_border=CELL_BORDER,
                                         anchor_element=self.anchor, driver=self.driver)
        self.viewport_mapper = GridViewportMapper(self.converter, self.driver)

class NavigationController:
    """Gère la navigation et l'interaction souris sur le plateau."""

    def __init__(self, driver, converter: Optional[CoordinateConverter] = None, viewport_mapper: Optional[GridViewportMapper] = None):
        self.driver = driver
        self.converter = converter
        self.viewport_mapper = viewport_mapper

    def get_coordinate_converter(self) -> Optional[CoordinateConverter]:
        """Retourne le convertisseur de coordonnées."""
        return self.converter

    def get_viewport_mapper(self) -> Optional[GridViewportMapper]:
        """Retourne le mapper de viewport."""
        return self.viewport_mapper

    def move_view_js(self, dx, dy):
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, "div#control")
            script = """
            const el = arguments[0];
            const dx = arguments[1];
            const dy = arguments[2];

            const rect = el.getBoundingClientRect();
            const startX = rect.left + rect.width / 2;
            const startY = rect.top + rect.height / 2;
            const endX = startX + dx;
            const endY = startY + dy;

            function createEvent(type, x, y, buttons = 1) {
                return new MouseEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: x,
                    clientY: y,
                    buttons: buttons,
                    button: 0
                });
            }

            el.dispatchEvent(createEvent('mousemove', startX, startY, 0));
            el.dispatchEvent(createEvent('mousedown', startX, startY, 1));
            el.dispatchEvent(createEvent('mousemove', startX + dx/2, startY + dy/2, 1));
            el.dispatchEvent(createEvent('mousemove', endX, endY, 1));
            el.dispatchEvent(createEvent('mouseup', endX, endY, 0));

            return `Moved ${dx}x${dy}`;
            """
            result = self.driver.execute_script(script, el, dx, dy)
            print(f"Déplacement JS de {dx}px horizontalement et {dy}px verticalement")
            print(f"DEBUG JS Result: {result}")
            self._log_move_view(dx, dy, success=True)
            return True
        except Exception as e:
            print("Erreur move_view_js:", e)
            import traceback; traceback.print_exc()
            self._log_move_view(dx, dy, success=False, error=str(e))
            return False

    def move_viewport(self, dx, dy, coord_system=None, wait_after=1.0, log=True, scale_factor=2.0):
        coord_ref = coord_system or self.converter
        if coord_ref is None:
            raise ValueError("CoordinateConverter requis pour déplacer la vue")

        if log:
            print(f"[NAVIGATION] Déplacement demandé: ({dx}, {dy}) px")

        before_info = coord_ref.get_viewport_bounds() if coord_ref else None

        # Appliquer le facteur d'échelle pour compenser le comportement du navigateur
        command_dx = int(round(dx * scale_factor))
        command_dy = int(round(dy * scale_factor))
        movement_result = self.move_view_js(command_dx, command_dy)
        
        if not movement_result:
            if log:
                print(f"[NAVIGATION] Échec du mouvement: ({dx}, {dy})")
            return {
                'success': False,
                'message': f"Échec du mouvement de ({dx}, {dy}) pixels",
                'dx': dx,
                'dy': dy,
                'before_position': before_info['grid_bounds'] if before_info else None,
                'after_position': None,
            }

        if wait_after > 0:
            time.sleep(wait_after)

        after_info = coord_ref.get_viewport_bounds() if coord_ref else None

        if log:
            print(f"[NAVIGATION] Mouvement appliqué: ({dx}, {dy}) px")

        return {
            'success': True,
            'message': f"Mouvement de ({dx}, {dy}) pixels effectué",
            'dx': dx,
            'dy': dy,
            'before_position': before_info['grid_bounds'] if before_info else None,
            'after_position': after_info['grid_bounds'] if after_info else None,
        }

    def execute_game_action(self, action, coord_system: Optional[CoordinateConverter] = None):
        if action is None:
            raise ValueError("Action invalide")

        grid_x = getattr(action, 'grid_x', None)
        grid_y = getattr(action, 'grid_y', None)
        if grid_x is None or grid_y is None:
            raise ValueError('GameAction doit contenir grid_x/grid_y')

        action_type = getattr(action, 'action_type', None)
        action_value = action_type.value if hasattr(action_type, 'value') else str(action_type)

        coord_ref = coord_system or self.converter
        if coord_ref is None:
            raise ValueError('CoordinateConverter requis pour exécuter une action')
        self.converter = coord_ref

        normalized_value = action_value.lower() if isinstance(action_value, str) else action_value

        if normalized_value in ("click_left", "ActionType.CLICK_LEFT"):
            return self.click_cell(grid_x, grid_y, right_click=False)
        if normalized_value in ("click_right", "ActionType.CLICK_RIGHT"):
            return self.click_cell(grid_x, grid_y, right_click=True)
        if normalized_value in ("double_click", "ActionType.DOUBLE_CLICK"):
            center_x, center_y = coord_ref.grid_to_screen_centered(grid_x, grid_y)
            return self._double_click_at(center_x, center_y)

        raise ValueError(f"Type d'action non supporté: {action_value}")

    def click_cell(self, grid_x, grid_y, right_click=False):
        if self.converter is None:
            raise ValueError("CoordinateConverter requis pour cliquer sur une cellule")

        try:
            center_x, center_y = self.converter.grid_to_screen_centered(grid_x, grid_y)
            try:
                target = self.driver.find_element(By.CSS_SELECTOR, "div#control canvas")
            except Exception:
                target = self.driver.find_element(By.CSS_SELECTOR, "div#control")

            click_event = 'contextmenu' if right_click else 'click'
            js = """
            const el = arguments[0];
            const screenX = arguments[1], screenY = arguments[2];
            const type = arguments[3];

            function makeMouse(type, x, y) {
                return new MouseEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: Math.round(x),
                    clientY: Math.round(y),
                    button: (type === 'contextmenu') ? 2 : 0
                });
            }

            el.dispatchEvent(makeMouse('mousemove', screenX, screenY));
            el.dispatchEvent(makeMouse('mousedown', screenX, screenY));
            el.dispatchEvent(makeMouse(type, screenX, screenY));
            el.dispatchEvent(makeMouse('mouseup', screenX, screenY));
            return true;
            """
            self.driver.execute_script(js, target, center_x, center_y, click_event)
            self._log_click_action(grid_x, grid_y, right_click, {
                'screen_x': center_x,
                'screen_y': center_y,
                'canvas_x': center_x,
                'canvas_y': center_y,
            })
            return True

        except Exception as e:
            print(f"\nERREUR: ERREUR lors du clic sur ({grid_x}, {grid_y}): {str(e)}")
            import traceback
            traceback.print_exc()
            save_bot_log("click_cell", {
                "grid_x": grid_x,
                "grid_y": grid_y,
                "right_click": right_click,
                "error": str(e)
            }, False)
            return False

    def _double_click_at(self, screen_x: float, screen_y: float, delay: float = 0.1) -> bool:
        try:
            body = self.driver.find_element(By.CSS_SELECTOR, "body")
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(body, screen_x, screen_y).double_click().perform()
            time.sleep(delay)
            return True
        except Exception as e:
            print(f"[ERREUR] Double-clic échoué ({screen_x:.0f}, {screen_y:.0f}): {e}")
            return False

    # Logging & diagnostics helpers -----------------------------------------------------------

    def _log_move_view(self, dx, dy, success: bool, error: str = None):
        payload = {
            "dx": dx,
            "dy": dy,
            "method": "javascript",
            "target": "canvas",
        }
        if error:
            payload["error"] = error
        save_bot_log("move_view", payload, success)

    def _log_click_action(self, grid_x, grid_y, right_click, conversion):
        save_bot_log("click_cell", {
            "grid_x": grid_x,
            "grid_y": grid_y,
            "right_click": right_click,
            "screen_x": conversion['screen_x'],
            "screen_y": conversion['screen_y'],
            "canvas_x": conversion['canvas_x'],
            "canvas_y": conversion['canvas_y'],
            "method": "javascript"
        }, True)
