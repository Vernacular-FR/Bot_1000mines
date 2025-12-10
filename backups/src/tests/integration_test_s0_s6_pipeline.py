"""
Integration Test - Validation complète du pipeline S0-S6

Test d'intégration qui valide le flux complet S0→S1→S2→S3→S4→S5→S6
avec les adaptateurs de compatibilité.
"""

import sys
import os
import time
import unittest
from unittest.mock import Mock, MagicMock
import numpy as np

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Imports des couches S0-S6
from lib.s0_navigation import BrowserNavigation, CoordinateConverter, InterfaceDetector
from lib.s1_capture import CaptureTrigger, PatchSegmenter, MetadataExtractor
from lib.s2_recognition import TemplateHierarchy, SmartMatcher, FrontierExtractor
from lib.s3_tensor import TensorGrid, HintCache, TraceRecorder
from lib.s4_solver import HybridSolver
from lib.s5_actionneur import ActionQueue, ActionExecutor, ActionLogger
from lib.s6_pathfinder import DensityAnalyzer, PathPlanner, ViewportScheduler
from lib.ops import MetricsCollector, AsyncLogger, PersistenceManager

# Imports des adaptateurs
from services.adapters import (
    SessionSetupAdapter, ActionExecutorAdapter, NavigationAdapter,
    ZoneCaptureAdapter, OptimizedAnalysisAdapter, GameSolverAdapter,
    GameLoopAdapter, GameLoopConfig
)


class TestS0S6PipelineIntegration(unittest.TestCase):
    """
    Tests d'intégration pour le pipeline S0-S6 complet
    """
    
    def setUp(self):
        """Configuration des tests"""
        # Mock du driver Selenium
        self.mock_driver = Mock()
        self.mock_driver.get = Mock()
        self.mock_driver.quit = Mock()
        
        # Mock des captures d'écran
        self.mock_screenshot = np.zeros((800, 1200, 3), dtype=np.uint8)
        self.mock_screenshot[:] = (50, 100, 150)  # Couleur de fond
        
        # Configuration de test
        self.test_config = GameLoopConfig(
            max_iterations=5,
            capture_interval=0.1,
            solving_timeout=5.0,
            action_delay=0.1
        )
    
    def test_session_setup_adapter_initialization(self):
        """Test l'initialisation de SessionSetupAdapter"""
        print("Testing SessionSetupAdapter initialization...")
        
        # Mock BrowserNavigation pour éviter les dépendances Selenium
        with unittest.mock.patch('services.adapters.s1_session_setup_adapter.webdriver') as mock_webdriver:
            mock_webdriver.Chrome = Mock(return_value=self.mock_driver)
            
            # Créer l'adaptateur de session
            session_adapter = SessionSetupAdapter(auto_close_browser=False)
            
            # Tester la configuration de session
            result = session_adapter.setup_session(difficulty="beginner")
            
            # Vérifications
            self.assertTrue(result, "Session setup should succeed")
            self.assertTrue(session_adapter.is_session_active(), "Session should be active")
            self.assertIsNotNone(session_adapter.get_driver(), "Driver should be available")
            self.assertIsNotNone(session_adapter.get_bot(), "Bot should be available")
            self.assertIsNotNone(session_adapter.get_coordinate_system(), "Coordinate system should be available")
            self.assertIsNotNone(session_adapter.get_tensor_grid(), "TensorGrid should be available")
            self.assertIsNotNone(session_adapter.get_action_executor(), "Action executor should be available")
            
            # Nettoyer
            session_adapter.cleanup_session()
    
    def test_navigation_adapter_compatibility(self):
        """Test la compatibilité de NavigationAdapter"""
        print("Testing NavigationAdapter compatibility...")
        
        # Créer les composants S0 mockés
        mock_browser_nav = Mock()
        mock_browser_nav.scroll_to = Mock(return_value=True)
        mock_browser_nav.get_viewport_info = Mock(return_value={
            'bounds': {'x_min': 0, 'y_min': 0, 'x_max': 1200, 'y_max': 800}
        })
        
        mock_coord_converter = Mock()
        mock_coord_converter.grid_to_screen = Mock(return_value=(400, 300))
        mock_coord_converter.screen_to_grid = Mock(return_value=(10, 15))
        
        mock_session_service = Mock()
        mock_session_service.get_driver = Mock(return_value=self.mock_driver)
        
        # Créer l'adaptateur
        nav_adapter = NavigationAdapter(
            browser_navigation=mock_browser_nav,
            coordinate_converter=mock_coord_converter,
            session_service=mock_session_service
        )
        
        # Tester les fonctions de compatibilité
        result = nav_adapter.move_viewport(100, 50, wait_after=0.1)
        self.assertTrue(result, "Viewport move should succeed")
        
        screen_coords = nav_adapter.grid_to_screen(10, 15)
        self.assertEqual(screen_coords, (400, 300), "Grid to screen conversion should work")
        
        grid_coords = nav_adapter.screen_to_grid(400, 300)
        self.assertEqual(grid_coords, (10, 15), "Screen to grid conversion should work")
        
        # Vérifier les statistiques
        stats = nav_adapter.get_navigation_stats()
        self.assertIn('viewport_moves', stats, "Stats should include viewport moves")
        self.assertIn('coordinate_conversions', stats, "Stats should include coordinate conversions")
    
    def test_zone_capture_adapter_compatibility(self):
        """Test la compatibilité de ZoneCaptureAdapter"""
        print("Testing ZoneCaptureAdapter compatibility...")
        
        # Créer les composants S1 mockés
        mock_capture_trigger = Mock()
        mock_capture_result = Mock()
        mock_capture_result.success = True
        mock_capture_result.screenshot = self.mock_screenshot
        mock_capture_trigger.trigger_manual_capture = Mock(return_value=mock_capture_result)
        
        mock_patch_segmenter = Mock()
        mock_segmentation_result = Mock()
        mock_segmentation_result.success = True
        mock_segmentation_result.get_cell_patches = Mock(return_value=[])
        mock_patch_segmenter.segment_full_viewport = Mock(return_value=mock_segmentation_result)
        
        mock_metadata_extractor = Mock()
        mock_extraction_result = Mock()
        mock_extraction_result.success = True
        mock_metadata_extractor.extract_batch_metadata = Mock(return_value=mock_extraction_result)
        
        mock_browser_nav = Mock()
        mock_coord_converter = Mock()
        
        # Créer l'adaptateur
        capture_adapter = ZoneCaptureAdapter(
            capture_trigger=mock_capture_trigger,
            patch_segmenter=mock_patch_segmenter,
            metadata_extractor=mock_metadata_extractor,
            browser_navigation=mock_browser_nav,
            coordinate_converter=mock_coord_converter
        )
        
        # Tester la capture
        screenshot = capture_adapter.capture_window()
        self.assertIsNotNone(screenshot, "Screenshot should be captured")
        
        # Tester l'extraction de patches
        patches = capture_adapter.extract_patches_from_capture(self.mock_screenshot)
        self.assertIsInstance(patches, list, "Patches should be a list")
        
        # Vérifier les statistiques
        stats = capture_adapter.get_capture_stats()
        self.assertIn('captures_performed', stats, "Stats should include captures performed")
    
    def test_optimized_analysis_adapter_compatibility(self):
        """Test la compatibilité de OptimizedAnalysisAdapter"""
        print("Testing OptimizedAnalysisAdapter compatibility...")
        
        # Créer les composants S2 mockés
        mock_template_hierarchy = Mock()
        mock_smart_matcher = Mock()
        mock_frontier_extractor = Mock()
        
        mock_patch_segmenter = Mock()
        mock_metadata_extractor = Mock()
        
        mock_tensor_grid = Mock()
        mock_tensor_grid.get_stats = Mock(return_value={'total_cells': 100})
        
        # Créer l'adaptateur
        analysis_adapter = OptimizedAnalysisAdapter(
            template_hierarchy=mock_template_hierarchy,
            smart_matcher=mock_smart_matcher,
            frontier_extractor=mock_frontier_extractor,
            patch_segmenter=mock_patch_segmenter,
            metadata_extractor=mock_metadata_extractor,
            tensor_grid=mock_tensor_grid
        )
        
        # Tester la reconnaissance de cellules
        recognized_cells = analysis_adapter.recognize_cells(self.mock_screenshot)
        self.assertIsInstance(recognized_cells, list, "Recognized cells should be a list")
        
        # Tester l'extraction de frontières
        frontier_cells = analysis_adapter.extract_frontier(self.mock_screenshot)
        self.assertIsInstance(frontier_cells, list, "Frontier cells should be a list")
        
        # Vérifier les statistiques
        stats = analysis_adapter.get_analysis_stats()
        self.assertIn('analyses_performed', stats, "Stats should include analyses performed")
    
    def test_game_solver_adapter_compatibility(self):
        """Test la compatibilité de GameSolverAdapter"""
        print("Testing GameSolverAdapter compatibility...")
        
        # Créer les composants S4 mockés
        mock_hybrid_solver = Mock()
        mock_solution = Mock()
        mock_solution.solver_engine = "csp"
        mock_solution.solving_time = 1.5
        mock_solution.confidence = 0.95
        mock_solution.cells_analyzed = 50
        mock_solution.moves = []
        mock_hybrid_solver.solve_grid = Mock(return_value=mock_solution)
        mock_hybrid_solver.get_safe_moves = Mock(return_value=[])
        mock_hybrid_solver.get_mine_probabilities = Mock(return_value={})
        mock_hybrid_solver.get_stats = Mock(return_value={'solutions_found': 1})
        
        mock_tensor_grid = Mock()
        mock_tensor_grid.get_stats = Mock(return_value={'total_cells': 100})
        
        mock_hint_cache = Mock()
        mock_hint_cache.get_stats = Mock(return_value={'hints_count': 0})
        
        mock_frontier_extractor = Mock()
        
        # Créer l'adaptateur
        solver_adapter = GameSolverAdapter(
            hybrid_solver=mock_hybrid_solver,
            tensor_grid=mock_tensor_grid,
            hint_cache=mock_hint_cache,
            frontier_extractor=mock_frontier_extractor
        )
        
        # Tester la résolution
        solution = solver_adapter.solve_current_state(timeout=5.0)
        self.assertIsNotNone(solution, "Solution should be found")
        self.assertTrue(solution.get('success', False), "Solution should be successful")
        
        # Tester les mouvements sûrs
        safe_moves = solver_adapter.get_safe_moves()
        self.assertIsInstance(safe_moves, list, "Safe moves should be a list")
        
        # Vérifier les statistiques
        stats = solver_adapter.get_solver_stats()
        self.assertIn('solving_attempts', stats, "Stats should include solving attempts")
    
    def test_action_executor_adapter_compatibility(self):
        """Test la compatibilité de ActionExecutorAdapter"""
        print("Testing ActionExecutorAdapter compatibility...")
        
        # Créer les composants S5 mockés
        mock_browser_nav = Mock()
        
        mock_action_queue = Mock()
        mock_action_queue.enqueue_action = Mock(return_value="action_123")
        mock_action_queue.get_queue_size = Mock(return_value=0)
        mock_action_queue.clear_queue = Mock(return_value=0)
        
        mock_action_executor = Mock()
        mock_action_result = Mock()
        mock_action_result.success = True
        mock_action_executor.execute_action = Mock(return_value=mock_action_result)
        mock_action_executor.process_action_queue = Mock(return_value=5)
        mock_action_executor.get_stats = Mock(return_value={'processed_count': 10})
        
        mock_action_logger = Mock()
        
        # Créer l'adaptateur
        action_adapter = ActionExecutorAdapter(
            browser_navigation=mock_browser_nav,
            action_queue=mock_action_queue,
            action_executor=mock_action_executor,
            action_logger=mock_action_logger
        )
        
        # Créer une action héritée
        from services.adapters.s4_action_executor_adapter import LegacyGameAction, LegacyActionType
        legacy_action = LegacyGameAction(
            action_type=LegacyActionType.CLICK_LEFT,
            grid_x=10,
            grid_y=15
        )
        
        # Tester l'exécution
        result = action_adapter.execute_action(legacy_action)
        self.assertTrue(result, "Action execution should succeed")
        
        # Tester les fonctions de compatibilité
        click_result = action_adapter.click_cell(10, 15)
        self.assertTrue(click_result, "Click cell should succeed")
        
        flag_result = action_adapter.flag_cell(20, 25)
        self.assertTrue(flag_result, "Flag cell should succeed")
        
        # Vérifier les statistiques
        stats = action_adapter.get_execution_stats()
        self.assertIn('actions_executed', stats, "Stats should include actions executed")
    
    def test_game_loop_adapter_orchestration(self):
        """Test l'orchestration de GameLoopAdapter"""
        print("Testing GameLoopAdapter orchestration...")
        
        # Mock tous les adaptateurs nécessaires
        mock_session_adapter = Mock()
        mock_session_adapter.is_session_active = Mock(return_value=True)
        mock_session_adapter.get_bot = Mock()
        mock_session_adapter.get_coordinate_system = Mock()
        mock_session_adapter.get_tensor_grid = Mock()
        mock_session_adapter.get_action_executor = Mock()
        
        mock_navigation_adapter = Mock()
        mock_navigation_adapter.get_navigation_stats = Mock(return_value={})
        
        mock_zone_capture_adapter = Mock()
        mock_zone_capture_adapter.capture_window = Mock(return_value=self.mock_screenshot)
        mock_zone_capture_adapter.get_capture_stats = Mock(return_value={})
        
        mock_analysis_adapter = Mock()
        mock_analysis_adapter.recognize_cells = Mock(return_value=[])
        mock_analysis_adapter.extract_frontier = Mock(return_value=[])
        mock_analysis_adapter.get_analysis_stats = Mock(return_value={})
        
        mock_solver_adapter = Mock()
        mock_solver_adapter.update_solver_with_recognition = Mock(return_value=True)
        mock_solver_adapter.solve_current_state = Mock(return_value={'has_solution': False})
        mock_solver_adapter.get_solver_stats = Mock(return_value={})
        
        mock_action_executor_adapter = Mock()
        mock_action_executor_adapter.get_execution_stats = Mock(return_value={})
        
        # Créer l'adaptateur de boucle de jeu
        game_loop_adapter = GameLoopAdapter(
            session_adapter=mock_session_adapter,
            navigation_adapter=mock_navigation_adapter,
            zone_capture_adapter=mock_zone_capture_adapter,
            analysis_adapter=mock_analysis_adapter,
            solver_adapter=mock_solver_adapter,
            action_executor_adapter=mock_action_executor_adapter
        )
        
        # Configurer pour un test rapide
        game_loop_adapter.set_config(self.test_config)
        
        # Tester la progression
        progress = game_loop_adapter.get_game_progress()
        self.assertIn('current_state', progress, "Progress should include current state")
        self.assertIn('current_iteration', progress, "Progress should include current iteration")
        
        # Tester les statistiques
        stats = game_loop_adapter.get_loop_stats()
        self.assertIn('navigation_stats', stats, "Stats should include navigation stats")
        self.assertIn('capture_stats', stats, "Stats should include capture stats")
    
    def test_optional_trace_recorder_handling(self):
        """Test la gestion de TraceRecorder optionnel dans Ops"""
        print("Testing Optional TraceRecorder handling in Ops...")
        
        # Tester avec TraceRecorder None
        metrics_collector = MetricsCollector(trace_recorder=None)
        metrics_collector.record_metric("test", 1.0)
        
        async_logger = AsyncLogger(trace_recorder=None)
        async_logger.info("test", "test message")
        
        # Les appels ne devraient pas lever d'exceptions
        self.assertTrue(True, "Optional TraceRecorder should be handled gracefully")
    
    def test_action_type_enum_mapping(self):
        """Test le mapping des énumérations ActionType"""
        print("Testing ActionType enum mapping...")
        
        # Vérifier qu'il n'y a pas de conflit entre les énumérations
        from services.adapters.s4_action_executor_adapter import LegacyActionType
        from lib.s5_actionneur import ActionType
        
        # Les énumérations devraient être distinctes
        self.assertNotEqual(LegacyActionType.CLICK_LEFT, ActionType.CLICK_CELL)
        self.assertNotEqual(LegacyActionType.CLICK_RIGHT, ActionType.FLAG_CELL)
        
        # Le mapping devrait fonctionner correctement
        action_adapter = ActionExecutorAdapter(
            browser_navigation=Mock(),
            action_queue=Mock(),
            action_executor=Mock(),
            action_logger=Mock()
        )
        
        # Le mapping interne devrait fonctionner
        self.assertIn(LegacyActionType.CLICK_LEFT, action_adapter._action_type_mapping)
        self.assertIn(LegacyActionType.CLICK_RIGHT, action_adapter._action_type_mapping)
    
    def test_end_to_end_pipeline_simulation(self):
        """Test une simulation complète du pipeline S0-S6"""
        print("Testing end-to-end pipeline simulation...")
        
        # Créer une simulation complète avec tous les composants mockés
        # mais avec une vraie orchestration via les adaptateurs
        
        # Mock du driver et des composants de base
        mock_driver = Mock()
        mock_driver.get = Mock()
        
        # Mock SessionSetupAdapter
        with unittest.mock.patch('services.adapters.s1_session_setup_adapter.webdriver') as mock_webdriver:
            mock_webdriver.Chrome = Mock(return_value=mock_driver)
            
            session_adapter = SessionSetupAdapter(auto_close_browser=False)
            
            # Simuler une session réussie
            session_adapter._session_active = True
            session_adapter._browser_navigation = Mock()
            session_adapter._coordinate_converter = Mock()
            session_adapter._tensor_grid = Mock()
            session_adapter._action_executor = Mock()
            
            # Vérifier que tous les composants sont accessibles
            self.assertIsNotNone(session_adapter.get_bot())
            self.assertIsNotNone(session_adapter.get_coordinate_system())
            self.assertIsNotNone(session_adapter.get_tensor_grid())
            self.assertIsNotNone(session_adapter.get_action_executor())
            
            # Nettoyer
            session_adapter.cleanup_session()


def run_integration_tests():
    """Exécute tous les tests d'intégration"""
    print("=" * 60)
    print("DÉMARRAGE DES TESTS D'INTÉGRATION S0-S6")
    print("=" * 60)
    
    # Créer la suite de tests
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestS0S6PipelineIntegration)
    
    # Exécuter les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Afficher le résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS D'INTÉGRATION")
    print("=" * 60)
    print(f"Tests exécutés: {result.testsRun}")
    print(f"Échecs: {len(result.failures)}")
    print(f"Erreurs: {len(result.errors)}")
    
    if result.failures:
        print("\nÉCHECS:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nERREURS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nRésultat global: {'SUCCÈS' if success else 'ÉCHEC'}")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    run_integration_tests()
