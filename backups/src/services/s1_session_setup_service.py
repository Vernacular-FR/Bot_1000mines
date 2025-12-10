#!/usr/bin/env python3
"""
Service de configuration de session - Navigation, initialisation et nettoyage
Gère toute la pile S0 → S6 sans passer par les anciens adaptateurs.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import sys

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from lib.config import (
    DIFFICULTY_CONFIG,
    DEFAULT_DIFFICULTY,
    GAME_CONFIG,
    GRID_REFERENCE_POINT,
    VIEWPORT_CONFIG,
    CELL_SIZE,
    CELL_BORDER,
    WAIT_TIMES,
)

from lib.s0_navigation import BrowserNavigation, CoordinateConverter, InterfaceDetector
from lib.s0_navigation.browser_manager import BrowserManager
from lib.s1_capture import CaptureTrigger, PatchSegmenter, MetadataExtractor
from lib.s2_recognition import TemplateHierarchy, SmartMatcher, FrontierExtractor
from lib.s3_tensor import TensorGrid, HintCache, TraceRecorder
from lib.s3_tensor.tensor_grid import GridBounds
from lib.s4_solver import HybridSolver
from lib.s5_actionneur import ActionQueue, ActionExecutor, ActionLogger
from lib.s6_pathfinder import DensityAnalyzer, PathPlanner, ViewportScheduler
from lib.ops import MetricsCollector, AsyncLogger, PersistenceManager
from .s1_navigation_service import NavigationService

# ------------------------------------------------------------------ #
# Legacy adapters (MineSweeperBot + CoordinateSystem) for navigation #
# ------------------------------------------------------------------ #
LEGACY_LIB_ROOT = Path(__file__).resolve().parents[2] / "backups"
if LEGACY_LIB_ROOT.exists() and str(LEGACY_LIB_ROOT) not in sys.path:
    sys.path.append(str(LEGACY_LIB_ROOT))

try:  # Optional legacy components, not required for core flow
    from lib.s1_interaction.game_controller import MineSweeperBot  # type: ignore
except Exception:  # pragma: no cover
    MineSweeperBot = None

try:
    from lib.s1_interaction.coordinate_system import CoordinateSystem  # type: ignore
except Exception:  # pragma: no cover
    CoordinateSystem = None


class GameSetupController:
    """Simplified controller that configures the Minesweeper difficulty via Selenium."""

    def __init__(self, driver):
        self.driver = driver
        self.selected_difficulty: Optional[str] = None

    @staticmethod
    def get_difficulty_from_user() -> str:
        """Fallback difficulty selection (no interactive prompt)."""
        return DEFAULT_DIFFICULTY

    def select_game_mode(self, difficulty: str) -> bool:
        """Sélectionne le mode Infinite puis applique la difficulté voulue."""
        self.selected_difficulty = (difficulty or DEFAULT_DIFFICULTY).lower()
        if not self.driver:
            print("[GAME] Aucun driver Selenium disponible, sélection ignorée.")
            return True

        try:
            wait = WebDriverWait(self.driver, WAIT_TIMES.get("page_load", 10))
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/#infinite'] button")))

            infinite_button = self.driver.find_element(By.CSS_SELECTOR, "a[href='/#infinite'] button")
            infinite_button.click()
            print("[GAME] Mode Infinite sélectionné")
            time.sleep(1)

            difficulty_config = DIFFICULTY_CONFIG.get(self.selected_difficulty, DIFFICULTY_CONFIG[DEFAULT_DIFFICULTY])
            difficulty_id = difficulty_config.get("selenium_id")

            if difficulty_id:
                script = """
                const target = document.querySelector(arguments[0]);
                if (target) {
                    target.click();
                    return true;
                }
                return false;
                """
                success = self.driver.execute_script(script, f"#{difficulty_id}")
                if success:
                    print(f"[GAME] Difficulté {difficulty_config['name']} sélectionnée")
                else:
                    print(f"[GAME] Élément #{difficulty_id} introuvable, tentative alternative")
                    self.driver.execute_script("const btn=document.querySelector('[id*=\"new-game\"]'); if(btn){btn.click();}")
            else:
                print(f"[GAME] Pas d'ID Selenium pour {self.selected_difficulty}, difficulté inchangée")

            return True
        except Exception as err:
            print(f"[GAME] Erreur lors de la sélection du mode: {err}")
            return True


class SessionState:
    """Minimal session metadata holder (game id, iteration, difficulty)."""

    def __init__(self):
        self.game_id: Optional[str] = None
        self.iteration_num: int = 1
        self.session_start_time: Optional[datetime] = None
        self.difficulty: Optional[str] = None

    def spawn_new_game(self, difficulty: Optional[str] = None) -> str:
        self.game_id = time.strftime("%Y%m%d_%H%M%S")
        self.iteration_num = 1
        self.session_start_time = datetime.now()
        if difficulty:
            self.difficulty = difficulty
        return self.game_id

    def increment_iteration(self) -> int:
        self.iteration_num += 1
        return self.iteration_num

    @classmethod
    def create_new_session(cls):
        return {"state": cls(), "storage": SessionStorage()}

    def is_active(self) -> bool:
        return self.game_id is not None and self.session_start_time is not None


class SessionStorage:
    """Handles temp/games folder creation and cleanup."""

    def __init__(self, root_dir: str = "temp/games"):
        self.root_dir = Path(root_dir)

    def cleanup_old_games(self, max_games_to_keep: int = 3) -> None:
        if not self.root_dir.exists():
            return

        try:
            game_dirs = sorted(
                [d for d in self.root_dir.iterdir() if d.is_dir()],
                key=lambda p: p.name,
                reverse=True,
            )
            for extra_dir in game_dirs[max_games_to_keep:]:
                shutil.rmtree(extra_dir, ignore_errors=True)
                print(f"[CLEANUP] Ancienne partie supprimée: {extra_dir.name}")
        except Exception as err:
            print(f"[CLEANUP] Erreur nettoyage: {err}")

    def build_game_paths(self, game_id: str) -> Dict[str, str]:
        base = self.root_dir / game_id
        return {
            "base": str(base),
            "interface": str(base / "s0_interface"),
            "zone": str(base / "s1_zone"),
            "analysis": str(base / "s2_analysis"),
            "solver": str(base / "s3_solver"),
            "actions": str(base / "s4_actions"),
            "metadata": str(base / "metadata.json"),
        }

    def ensure_storage_ready(self, state: SessionState, create_metadata: bool = True):
        if not state.game_id:
            raise ValueError("Aucune partie initialisée.")

        paths = self.build_game_paths(state.game_id)
        base_path = Path(paths["base"])
        base_path.mkdir(parents=True, exist_ok=True)

        for key, path in paths.items():
            if key == "metadata":
                continue
            Path(path).mkdir(parents=True, exist_ok=True)

        if create_metadata:
            self._ensure_metadata_file(paths["metadata"], state)

        return {"paths": paths, "base_path": str(base_path)}

    @staticmethod
    def _ensure_metadata_file(metadata_path: str, state: SessionState) -> None:
        metadata_file = Path(metadata_path)
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "game_id": state.game_id,
            "difficulty": state.difficulty,
            "start_time": (state.session_start_time or datetime.now()).isoformat(),
            "initial_iteration": state.iteration_num,
        }
        metadata_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class SessionSetupService:
    """Service de configuration complète de session de jeu (S0 → S6)."""

    legacy_bot: Optional[Any] = None
    legacy_coordinate_system: Optional[Any] = None

    def __init__(self, auto_close_browser: bool = True):
        self.auto_close_browser = auto_close_browser

        # Gestion navigateur
        self.browser_manager: Optional[BrowserManager] = None
        self.driver = None

        # Contrôleur legacy (choix difficulté)
        self.session_controller: Optional[GameSetupController] = None
        self.s1_capture: Optional[Any] = None
        self.s1_navigation: Optional[NavigationService] = None
        self.s1_segmenter: Optional[Any] = None

        # Composants S0
        self.browser_navigation: Optional[BrowserNavigation] = None
        self.coordinate_converter: Optional[CoordinateConverter] = None
        self.interface_detector: Optional[InterfaceDetector] = None
        self.navigation_service: Optional[NavigationService] = None

        # Composants S1
        self.capture_trigger: Optional[CaptureTrigger] = None
        self.patch_segmenter: Optional[PatchSegmenter] = None
        self.metadata_extractor: Optional[MetadataExtractor] = None

        # Composants S2
        self.template_hierarchy: Optional[TemplateHierarchy] = None
        self.smart_matcher: Optional[SmartMatcher] = None
        self.frontier_extractor: Optional[FrontierExtractor] = None

        # Composants S3
        self.trace_recorder: Optional[TraceRecorder] = None
        self.tensor_grid: Optional[TensorGrid] = None
        self.hint_cache: Optional[HintCache] = None

        # Composant S4
        self.hybrid_solver: Optional[HybridSolver] = None

        # Composants S5
        self.action_queue: Optional[ActionQueue] = None
        self.action_executor: Optional[ActionExecutor] = None
        self.action_logger: Optional[ActionLogger] = None

        # Composants S6
        self.density_analyzer: Optional[DensityAnalyzer] = None
        self.path_planner: Optional[PathPlanner] = None
        self.viewport_scheduler: Optional[ViewportScheduler] = None

        # Ops
        self.metrics_collector: Optional[MetricsCollector] = None
        self.async_logger: Optional[AsyncLogger] = None
        self.persistence_manager: Optional[PersistenceManager] = None

        # État
        self.is_initialized = False
        self.game_session = None
        self.session_paths: Optional[Dict[str, str]] = None
        self.initial_grid_bounds: Optional[GridBounds] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def setup_session(self, difficulty: Optional[str] = None) -> Dict[str, Any]:
        """Configure la pile complète et prépare la partie."""
        try:
            print("[SESSION] Initialisation complète S0→S6 ...")

            self._prepare_game_session(difficulty)
            difficulty = difficulty or self.game_session["state"].difficulty

            if not self._setup_browser():
                return self._failure("browser_start_failed", "Impossible de démarrer Chrome")

            if not self._initialize_stacks():
                return self._failure("stack_init_failed", "Échec d'initialisation d'une couche S0→S6")

            if not self._navigate_to_game():
                return self._failure("navigation_failed", "Impossible d'ouvrir le site de jeu")

            if not self._configure_game_mode(difficulty):
                return self._failure("game_setup_failed", "Impossible de sélectionner la difficulté")

            self._calibrate_coordinate_converter()

            config = DIFFICULTY_CONFIG.get(difficulty, DIFFICULTY_CONFIG[DEFAULT_DIFFICULTY])

            self.is_initialized = True
            print(f"[SESSION] ✅ Session prête (mode {config['name']})")

            return {
                "success": True,
                "difficulty": difficulty,
                "config": config,
                "driver": self.driver,
                "browser_navigation": self.browser_navigation,
                "coordinate_converter": self.coordinate_converter,
                "capture_trigger": self.capture_trigger,
                "patch_segmenter": self.patch_segmenter,
                "smart_matcher": self.smart_matcher,
                "tensor_grid": self.tensor_grid,
                "hybrid_solver": self.hybrid_solver,
                "action_queue": self.action_queue,
                "action_executor": self.action_executor,
            }

        except Exception as err:  # pragma: no cover (log + remontée)
            return self._failure("unexpected_error", str(err))

    def cleanup_session(self) -> bool:
        """Ferme toutes les ressources."""
        print("[CLEANUP] Nettoyage de la session ...")

        try:
            if self.async_logger:
                self.async_logger.shutdown()
            if self.persistence_manager:
                self.persistence_manager.shutdown()
            if self.metrics_collector:
                self.metrics_collector.shutdown()

            if self.browser_manager:
                if not self.auto_close_browser:
                    input("Appuyez sur Entrée pour fermer le navigateur ...")
                self.browser_manager.stop_browser()

            self.__init__(auto_close_browser=self.auto_close_browser)
            print("[CLEANUP] ✅ Session nettoyée")
            return True
        except Exception as err:  # pragma: no cover
            print(f"[CLEANUP] ❌ Erreur: {err}")
            return False

    # ------------------------------------------------------------------ #
    # Getters (compatibilité et nouvelle API)
    # ------------------------------------------------------------------ #
    def _ensure_ready(self):
        if not self.is_initialized:
            raise RuntimeError("La session n'est pas initialisée. Appelez setup_session().")

    def get_driver(self):
        self._ensure_ready()
        return self.driver

    def get_browser_navigation(self):
        self._ensure_ready()
        return self.browser_navigation

    def get_coordinate_converter(self):
        self._ensure_ready()
        return self.coordinate_converter

    def get_interface_detector(self):
        self._ensure_ready()
        return self.interface_detector

    def get_coordinate_system(self):
        self._ensure_ready()
        return self.legacy_coordinate_system

    def get_legacy_bot(self):
        self._ensure_ready()
        return self.legacy_bot

    def get_capture_trigger(self):
        self._ensure_ready()
        return self.capture_trigger

    def get_patch_segmenter(self):
        self._ensure_ready()
        return self.patch_segmenter

    def get_metadata_extractor(self):
        self._ensure_ready()
        return self.metadata_extractor

    def get_navigation_service(self):
        self._ensure_ready()
        if not self.navigation_service and self.driver:
            self.navigation_service = NavigationService(self.driver, session_service=self)
        return self.navigation_service

    def get_template_hierarchy(self):
        self._ensure_ready()
        return self.template_hierarchy

    def get_smart_matcher(self):
        self._ensure_ready()
        return self.smart_matcher

    def get_frontier_extractor(self):
        self._ensure_ready()
        return self.frontier_extractor

    def get_tensor_grid(self):
        self._ensure_ready()
        return self.tensor_grid

    def get_hint_cache(self):
        self._ensure_ready()
        return self.hint_cache

    def get_solver(self):
        self._ensure_ready()
        return self.hybrid_solver

    def get_action_queue(self):
        self._ensure_ready()
        return self.action_queue

    def get_action_executor(self):
        self._ensure_ready()
        return self.action_executor

    def get_action_logger(self):
        self._ensure_ready()
        return self.action_logger

    def get_path_planner(self):
        self._ensure_ready()
        return self.path_planner

    def get_viewport_scheduler(self):
        self._ensure_ready()
        return self.viewport_scheduler

    # ------------------------------------------------------------------ #
    # Étapes internes
    # ------------------------------------------------------------------ #
    def _prepare_game_session(self, difficulty: Optional[str]):
        self.game_session = SessionState.create_new_session()
        state = self.game_session["state"]
        storage = self.game_session["storage"]

        if not difficulty:
            difficulty = GameSetupController.get_difficulty_from_user()

        storage.cleanup_old_games(3)
        state.spawn_new_game(difficulty)
        storage_info = storage.ensure_storage_ready(state, create_metadata=True)
        if storage_info and "paths" in storage_info:
            self.session_paths = storage_info["paths"]

    def _setup_browser(self) -> bool:
        if self.browser_manager and self.driver:
            return True

        self.browser_manager = BrowserManager()
        if not self.browser_manager.start_browser():
            return False

        self.driver = self.browser_manager.get_driver()
        self.session_controller = GameSetupController(self.driver)

        if MineSweeperBot and not self.legacy_bot:
            try:
                self.legacy_bot = MineSweeperBot(self.driver)
                if hasattr(self.legacy_bot, "coord_system"):
                    self.legacy_coordinate_system = getattr(self.legacy_bot, "coord_system")
            except Exception as err:
                print(f"[SESSION] Legacy bot unavailable: {err}")

        if CoordinateSystem and not self.legacy_coordinate_system:
            try:
                self.legacy_coordinate_system = CoordinateSystem(driver=self.driver)
                if hasattr(self.legacy_coordinate_system, "setup_anchor"):
                    try:
                        self.legacy_coordinate_system.setup_anchor()
                    except Exception:
                        pass
            except Exception as err:
                print(f"[SESSION] Legacy coordinate system unavailable: {err}")

        return True

    def _initialize_stacks(self) -> bool:
        stack_sequence = [
            ("S0", self._initialize_s0_stack),
            ("S1", self._initialize_s1_stack),
            ("S2", self._initialize_s2_stack),
            ("S3", self._initialize_s3_stack),
            ("S4", self._initialize_s4_stack),
            ("S5", self._initialize_s5_stack),
            ("S6", self._initialize_s6_stack),
            ("OPS", self._initialize_ops_stack),
        ]

        for label, initializer in stack_sequence:
            if not initializer():
                print(f"[SESSION] ❌ Échec lors de l'initialisation {label}")
                return False
            print(f"[SESSION] ✅ {label} initialisé")
        return True

    def _navigate_to_game(self) -> bool:
        url = GAME_CONFIG.get("url")
        if not url:
            return True
        return self.browser_manager.navigate_to(url)

    def _configure_game_mode(self, difficulty: str) -> bool:
        if not self.session_controller:
            return False
        return self.session_controller.select_game_mode(difficulty)

    # ---- Initialisation des piles ------------------------------------ #
    def _initialize_s0_stack(self) -> bool:
        try:
            self.browser_navigation = BrowserNavigation(self.driver)
            self.coordinate_converter = CoordinateConverter(
                cell_size=CELL_SIZE,
                cell_border=CELL_BORDER,
            )
            anchor_x, anchor_y = GRID_REFERENCE_POINT
            self.coordinate_converter.set_anchor_offset(anchor_x, anchor_y)
            viewport_offset = VIEWPORT_CONFIG.get("position", (0, 0))
            self.coordinate_converter.set_viewport_offset(*viewport_offset)
            self.interface_detector = InterfaceDetector()
            if not self.navigation_service and self.driver:
                self.navigation_service = NavigationService(self.driver, session_service=self)
            return True
        except Exception as err:
            print(f"S0 stack initialization failed: {err}")
            return False

    def _initialize_s1_stack(self) -> bool:
        try:
            self.capture_trigger = CaptureTrigger(
                navigation=self.browser_navigation,
                coordinate_converter=self.coordinate_converter,
                max_capture_rate=10.0,
                enable_periodic_capture=False,
                periodic_interval=1.0,
                capture_timeout=WAIT_TIMES.get("element", 10),
            )
            self.patch_segmenter = PatchSegmenter(
                coordinate_converter=self.coordinate_converter,
                patch_margin=2,
                enable_interface_masking=True,
                min_patch_size=10,
            )
            self.metadata_extractor = MetadataExtractor(
                coordinate_converter=self.coordinate_converter
            )
            return True
        except Exception as err:
            print(f"S1 stack initialization failed: {err}")
            return False

    def _initialize_s2_stack(self) -> bool:
        try:
            self.template_hierarchy = TemplateHierarchy()
            self.frontier_extractor = FrontierExtractor(
                tensor_grid=None,
                hint_cache=None,
            )
            return True
        except Exception as err:
            print(f"S2 stack initialization failed: {err}")
            return False

    def _initialize_s3_stack(self) -> bool:
        try:
            trace_output = Path("temp/traces")
            trace_output.mkdir(parents=True, exist_ok=True)
            self.trace_recorder = TraceRecorder(
                output_dir=trace_output,
                session_id=f"s3_session_{int(time.time())}",
            )

            from lib.s3_tensor.tensor_grid import GridBounds

            bounds = GridBounds(-50, -50, 50, 50)
            self.tensor_grid = TensorGrid(bounds)
            self.hint_cache = HintCache()

            if self.smart_matcher:
                self.smart_matcher.tensor_grid = self.tensor_grid
            if self.frontier_extractor:
                self.frontier_extractor.tensor_grid = self.tensor_grid
                self.frontier_extractor.hint_cache = self.hint_cache

            return True
        except Exception as err:
            print(f"S3 stack initialization failed: {err}")
            return False

    def _initialize_s4_stack(self) -> bool:
        try:
            self.hybrid_solver = HybridSolver(
                tensor_grid=self.tensor_grid,
                hint_cache=self.hint_cache,
            )
            return True
        except Exception as err:
            print(f"S4 stack initialization failed: {err}")
            return False

    def _initialize_s5_stack(self) -> bool:
        try:
            self.action_queue = ActionQueue(tensor_grid=self.tensor_grid)
            self.action_executor = ActionExecutor(
                tensor_grid=self.tensor_grid,
                navigation_primitives=self.browser_navigation,
            )
            self.action_logger = ActionLogger(
                tensor_grid=self.tensor_grid,
                hint_cache=self.hint_cache,
            )
            return True
        except Exception as err:
            print(f"S5 stack initialization failed: {err}")
            return False

    def _initialize_s6_stack(self) -> bool:
        try:
            self.density_analyzer = DensityAnalyzer(
                tensor_grid=self.tensor_grid,
                hint_cache=self.hint_cache,
            )
            self.path_planner = PathPlanner(
                density_analyzer=self.density_analyzer,
                tensor_grid=self.tensor_grid,
                hint_cache=self.hint_cache,
            )
            self.viewport_scheduler = ViewportScheduler(
                tensor_grid=self.tensor_grid,
                hint_cache=self.hint_cache,
                density_analyzer=self.density_analyzer,
                path_planner=self.path_planner,
            )
            return True
        except Exception as err:
            print(f"S6 stack initialization failed: {err}")
            return False

    def _initialize_ops_stack(self) -> bool:
        try:
            if self.trace_recorder:
                self.metrics_collector = MetricsCollector(
                    trace_recorder=self.trace_recorder
                )
                self.async_logger = AsyncLogger(
                    trace_recorder=self.trace_recorder,
                    enable_console_output=True,
                )
                from lib.ops.persistence import BackupConfig, BackupFrequency, PersistenceFormat

                backup_cfg = BackupConfig(
                    frequency=BackupFrequency.HOURLY,
                    format=PersistenceFormat.JSON,
                    backup_path="backups",
                )
                self.persistence_manager = PersistenceManager(
                    trace_recorder=self.trace_recorder,
                    backup_config=backup_cfg,
                )
            return True
        except Exception as err:
            print(f"Ops stack initialization failed: {err}")
            return False

    # ------------------------------------------------------------------ #
    def _calibrate_coordinate_converter(self) -> None:
        """Ajuste l'anchor et la taille réelle des cellules après chargement du jeu."""
        if not self.coordinate_converter or not self.driver or not self.browser_navigation:
            return

        if self._apply_coordinate_system_alignment():
            return

        if self._apply_dom_geometry_calibration():
            return

        if self._apply_interface_zone_calibration():
            return

        self._apply_basic_viewport_calibration()
        self._apply_cell_measurement_calibration()

    def _apply_dom_geometry_calibration(self) -> bool:
        """Utilise la structure DOM pour calculer l'anchor et la taille de grille."""
        try:
            measurements = self.driver.execute_script(
                """
                const board = document.querySelector('#control .game-board, .game-board');
                const firstCell = board ? board.querySelector('.cell') : document.querySelector('.cell');
                if (!board || !firstCell) {
                    return null;
                }
                const boardRect = board.getBoundingClientRect();
                const cellRect = firstCell.getBoundingClientRect();
                const cols = Math.max(1, Math.round(boardRect.width / cellRect.width));
                const rows = Math.max(1, Math.round(boardRect.height / cellRect.height));
                return {
                    cellSize: Math.round(cellRect.width),
                    gridOriginX: Math.round(cellRect.left + window.scrollX),
                    gridOriginY: Math.round(cellRect.top + window.scrollY),
                    cols: cols,
                    rows: rows
                };
                """
            )
        except Exception as err:
            print(f"[S0] Mesure DOM impossible: {err}")
            return False

        if not measurements or not measurements.get("cellSize"):
            return False

        self.coordinate_converter.calibrate_cell_size(int(measurements["cellSize"]))
        self.coordinate_converter.set_anchor_offset(
            int(measurements["gridOriginX"]),
            int(measurements["gridOriginY"]),
        )
        self.coordinate_converter.set_viewport_offset(0, 0)

        cols = max(1, int(measurements.get("cols") or 0))
        rows = max(1, int(measurements.get("rows") or 0))
        if cols and rows:
            self.initial_grid_bounds = GridBounds(0, 0, cols - 1, rows - 1)
        return True

    def _apply_interface_zone_calibration(self) -> bool:
        """Tente de caler l’anchor et la zone grille via le détecteur d’interface legacy."""
        try:
            from _old.lib.s1_interaction.interface_detector import InterfaceDetector as LegacyInterfaceDetector
        except ImportError:
            return False

        interface_dir = None
        if self.session_paths and "interface" in self.session_paths:
            interface_dir = Path(self.session_paths["interface"])
        else:
            interface_dir = Path("temp/interface")
        interface_dir.mkdir(parents=True, exist_ok=True)

        try:
            detector = LegacyInterfaceDetector(self.driver, {"interface": str(interface_dir)})
        except Exception as err:
            print(f"[S0] Legacy InterfaceDetector indisponible: {err}")
            return False

        if not detector.detect_interface_positions():
            return False

        pixel_zone = detector.calculate_internal_zone_pixels()
        if not pixel_zone:
            return False

        anchor_x = int(pixel_zone["left"])
        anchor_y = int(pixel_zone["top"])
        self.coordinate_converter.set_anchor_offset(anchor_x, anchor_y)
        self.coordinate_converter.set_viewport_offset(0, 0)

        cell_size = self.coordinate_converter.get_effective_cell_size()
        width_px = max(1, int(pixel_zone["right"] - pixel_zone["left"]))
        height_px = max(1, int(pixel_zone["bottom"] - pixel_zone["top"]))
        grid_width = max(1, width_px // cell_size)
        grid_height = max(1, height_px // cell_size)
        self.initial_grid_bounds = GridBounds(0, 0, grid_width - 1, grid_height - 1)
        return True

    def _apply_coordinate_system_alignment(self) -> bool:
        """Utilise le CoordinateSystem legacy pour aligner immédiatement le converter."""
        if not self.legacy_coordinate_system or not self.coordinate_converter:
            return False

        try:
            if hasattr(self.legacy_coordinate_system, "setup_anchor"):
                self.legacy_coordinate_system.setup_anchor()
            anchor_pos = self.legacy_coordinate_system.get_anchor_css_position()
            anchor_x = int(anchor_pos.get("x", 0))
            anchor_y = int(anchor_pos.get("y", 0))
            self.coordinate_converter.set_anchor_offset(anchor_x, anchor_y)
            self.coordinate_converter.set_viewport_offset(0, 0)
            if hasattr(self.legacy_coordinate_system, "cell_total"):
                cell_size = int(getattr(self.legacy_coordinate_system, "cell_total", CELL_SIZE))
                if cell_size > 0:
                    self.coordinate_converter.calibrate_cell_size(cell_size)
            return True
        except Exception as err:
            print(f"[S0] Legacy coordinate alignment failed: {err}")
            return False

    def _apply_basic_viewport_calibration(self) -> None:
        """Utilise le viewport S0 pour estimer l’ancrage si aucune détection fiable."""
        try:
            viewport = self.browser_navigation.get_current_viewport()
            if viewport:
                anchor_x = int(viewport[0])
                anchor_y = int(viewport[1])
                self.coordinate_converter.set_anchor_offset(anchor_x, anchor_y)
                self.coordinate_converter.set_viewport_offset(0, 0)
        except Exception as err:
            print(f"[S0] Impossible de récupérer le viewport courant: {err}")

    def _apply_cell_measurement_calibration(self) -> None:
        """Mesure la taille d’une cellule pour affiner la calibration."""
        try:
            cell_measurements = self.driver.execute_script(
                """
                const selectorList = [
                    '.cell',
                    '.game-board .cell',
                    '#gameCanvas + div .cell',
                    '#control .cell'
                ];
                let target = null;
                for (const selector of selectorList) {
                    const el = document.querySelector(selector);
                    if (el) { target = el; break; }
                }
                if (!target) {
                    return null;
                }
                const box = target.getBoundingClientRect();
                return {
                    cellSize: Math.round(box.width),
                    screenX: Math.round(box.left + window.scrollX),
                    screenY: Math.round(box.top + window.scrollY)
                };
                """
            )

            if cell_measurements and cell_measurements.get("cellSize"):
                self.coordinate_converter.calibrate_cell_size(int(cell_measurements["cellSize"]))
                if cell_measurements.get("screenX") is not None and cell_measurements.get("screenY") is not None:
                    self.coordinate_converter.set_anchor_offset(
                        int(cell_measurements["screenX"]),
                        int(cell_measurements["screenY"]),
                    )
        except Exception as err:
            print(f"[S0] Impossible de calibrer la taille des cellules: {err}")

    # ------------------------------------------------------------------ #
    def _failure(self, error_code: str, message: str) -> Dict[str, Any]:
        return {"success": False, "error": error_code, "message": message}
