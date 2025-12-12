from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from src.lib.s1_capture import (
    CaptureController,
    CaptureRequest,
    CaptureResult,
)
from src.lib.s1_capture.s11_canvas_capture import CanvasCaptureBackend

from .s00_browser_manager import BrowserManager
from .s03_Coordonate_system import CoordinateConverter, CanvasLocator
from .s03_game_controller import NavigationController
from .s04_viewport_mapper import ViewportMapper
from .s05_status_reader import StatusReader
from .api import GameStatus


@dataclass
class ViewportState:
    anchor_position: Tuple[float, float]
    viewport_bounds: Optional[Dict] = None


@dataclass
class CanvasDescriptor:
    id: str
    tile: Tuple[int, int]
    screen_left: float
    screen_top: float
    width: float
    height: float
    relative_left: float
    relative_top: float


class InterfaceController:
    """
    Façade s0 : rassemble BrowserManager, CoordinateConverter/CanvasLocator
    et NavigationController pour exposer une API simple aux couches supérieures.
    """

    def __init__(
        self,
        browser: BrowserManager,
        converter: CoordinateConverter,
        locator: CanvasLocator,
        navigator: NavigationController,
        status_reader: Optional[StatusReader] = None,
        capture_controller: Optional[CaptureController] = None,
    ):
        self.browser = browser
        self.converter = converter
        self.locator = locator
        self.navigator = navigator
        self.status_reader = status_reader
        self._state: Optional[ViewportState] = None
        self._capture_controller = capture_controller

    @classmethod
    def from_browser(cls, browser: BrowserManager) -> "InterfaceController":
        driver = browser.get_driver()
        if driver is None:
            raise RuntimeError("Le navigateur doit être démarré avant d'instancier InterfaceController.")

        converter = CoordinateConverter(driver=driver)
        converter.setup_anchor()
        locator = converter.canvas_locator
        locator.set_driver(driver)

        viewport_mapper = ViewportMapper(converter, driver)
        navigator = NavigationController(driver, converter=converter, viewport_mapper=viewport_mapper)
        status_reader = StatusReader(driver)

        controller = cls(
            browser,
            converter,
            locator,
            navigator,
            status_reader=status_reader,
        )
        controller._capture_controller = CaptureController(
            interface=controller,
            canvas_backend=CanvasCaptureBackend(driver),
            viewport_mapper=navigator.viewport_mapper,
        )
        controller.refresh_state()
        return controller

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def refresh_state(self) -> ViewportState:
        anchor = self.converter.get_anchor_css_position()
        viewport_bounds = None
        try:
            viewport_bounds = self.converter.canvas_locator.locate("0x0")  # ensure anchor valid
        except Exception:
            pass

        self._state = ViewportState(
            anchor_position=(anchor["x"], anchor["y"]),
            viewport_bounds=viewport_bounds,
        )
        return self._state

    def ensure_visible(self, grid_bounds: Tuple[int, int, int, int]):
        """
        Demande au NavigationController de repositionner la vue pour que la zone soit visible.
        grid_bounds = (left, top, right, bottom).
        """
        if not self.navigator.viewport_mapper:
            return

        target_left, target_top, target_right, target_bottom = grid_bounds
        current = self.navigator.viewport_mapper.get_viewport_bounds()
        if not current:
            return

        cur_left, cur_top, cur_right, cur_bottom = current["grid_bounds"]
        dx = 0
        dy = 0

        if target_left < cur_left:
            dx = (target_left - cur_left) * self.converter.cell_total
        elif target_right > cur_right:
            dx = (target_right - cur_right) * self.converter.cell_total

        if target_top < cur_top:
            dy = (target_top - cur_top) * self.converter.cell_total
        elif target_bottom > cur_bottom:
            dy = (target_bottom - cur_bottom) * self.converter.cell_total

        if dx or dy:
            self.navigator.move_viewport(dx, dy, coord_system=self.converter, log=True)
            self.refresh_state()

    # ------------------------------------------------------------------
    # Canvas helpers -> alimenter CaptureMeta (taille cellule, offsets)
    # ------------------------------------------------------------------

    def locate_canvas_for_point(self, canvas_x: float, canvas_y: float) -> Optional[CanvasDescriptor]:
        descriptor = self.locator.find_canvas_for_point(canvas_x, canvas_y)
        if descriptor is None:
            return None
        return CanvasDescriptor(**descriptor)

    def get_capture_meta(self, canvas_x: float, canvas_y: float) -> Optional[Dict]:
        descriptor = self.locate_canvas_for_point(canvas_x, canvas_y)
        if descriptor is None:
            return None

        return {
            "canvas_id": descriptor.id,
            "tile": descriptor.tile,
            "relative_origin": (descriptor.relative_left, descriptor.relative_top),
            "size": (descriptor.width, descriptor.height),
            "cell_size": self.converter.cell_size,
        }

    # ------------------------------------------------------------------
    # Navigation wrappers
    # ------------------------------------------------------------------

    def scroll(self, dx: float, dy: float):
        self.navigator.move_viewport(dx, dy, coord_system=self.converter, log=True)
        self.refresh_state()

    def click_canvas_point(self, canvas_x: float, canvas_y: float):
        screen_x, screen_y = self.converter.canvas_to_screen(canvas_x, canvas_y)
        self.navigator.click_screen(screen_x, screen_y)

    def click_grid_cell(self, grid_x: int, grid_y: int):
        center_x, center_y = self.converter.grid_to_screen_centered(grid_x, grid_y)
        self.navigator.click_screen(center_x, center_y)

    # ------------------------------------------------------------------
    # Capture helpers (façade s1_capture)
    # ------------------------------------------------------------------

    def capture_zone(self, request: CaptureRequest) -> CaptureResult:
        return self._get_capture_controller().capture_zone(request)

    def capture_grid_window(
        self,
        grid_bounds: Tuple[int, int, int, int],
        *,
        save: bool = False,
        annotate: bool = False,
        filename: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> CaptureResult:
        return self._get_capture_controller().capture_grid_window(
            grid_bounds,
            save=save,
            annotate=annotate,
            filename=filename,
            bucket=bucket,
        )

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def read_game_status(self) -> GameStatus:
        """
        Retourne l'état courant du panneau #status (scores, vies, difficulté, bonus).
        """
        if not self.status_reader:
            driver = self.browser.get_driver()
            if driver is None:
                raise RuntimeError("Aucun driver disponible pour lire le status.")
            self.status_reader = StatusReader(driver)
        return self.status_reader.read_status()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_capture_controller(self) -> CaptureController:
        if self._capture_controller is not None:
            return self._capture_controller

        driver = self.browser.get_driver()
        if driver is None:
            raise RuntimeError("Aucun driver disponible pour initialiser CaptureController.")

        self._capture_controller = CaptureController(
            interface=self,
            canvas_backend=CanvasCaptureBackend(driver),
            viewport_mapper=self.navigator.viewport_mapper,
        )
        return self._capture_controller
