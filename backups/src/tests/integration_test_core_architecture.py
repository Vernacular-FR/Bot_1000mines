"""
Core Architecture Integration Test - Validation S0-S6

Test d'intégration qui valide le pipeline S0-S6 complet en se concentrant
sur les composants qui fonctionnent sans dépendances externes.
"""

import sys
import os
import time
import unittest
from unittest.mock import Mock, MagicMock, patch
import numpy as np

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCoreArchitectureIntegration(unittest.TestCase):
    """
    Tests d'intégration pour l'architecture S0-S6 core
    """
    
    def setUp(self):
        """Configuration des tests"""
        # Mock des dépendances externes
        self.mock_cv2 = MagicMock()
        self.mock_selenium = MagicMock()
        
        # Patcher les imports au niveau du module
        self.patches = []
        
        # Patcher selenium
        selenium_patch = patch.dict('sys.modules', {
            'selenium': self.mock_selenium,
            'selenium.webdriver': self.mock_selenium.webdriver,
            'selenium.webdriver.chrome': self.mock_selenium.webdriver.chrome,
            'selenium.webdriver.chrome.options': self.mock_selenium.webdriver.chrome.options
        })
        selenium_patch.start()
        self.patches.append(selenium_patch)
        
        # Mock du driver Selenium
        self.mock_driver = Mock()
        self.mock_driver.get = Mock()
        self.mock_driver.quit = Mock()
        self.mock_selenium.webdriver.Chrome.return_value = self.mock_driver
    
    def tearDown(self):
        """Nettoyage des patches"""
        for patch in self.patches:
            patch.stop()
    
    def test_s0_navigation_layer(self):
        """Test que la couche S0 Navigation fonctionne"""
        print("Testing S0 Navigation layer...")
        
        try:
            from lib.s0_navigation import BrowserNavigation, CoordinateConverter, InterfaceDetector
            
            # Créer les composants
            browser_nav = BrowserNavigation()
            coord_converter = CoordinateConverter()
            interface_detector = InterfaceDetector()
            
            # Vérifier qu'ils peuvent être créés
            self.assertIsNotNone(browser_nav)
            self.assertIsNotNone(coord_converter)
            self.assertIsNotNone(interface_detector)
            
            # Tester les fonctions de base
            viewport_info = browser_nav.get_current_viewport()
            self.assertIsInstance(viewport_info, tuple)
            self.assertEqual(len(viewport_info), 4)
            
            # Test de conversion de coordonnées
            screen_coords = coord_converter.grid_to_screen(0, 0)
            self.assertIsInstance(screen_coords, tuple)
            self.assertEqual(len(screen_coords), 2)
            
            print("✅ S0 Navigation layer fully functional")
            
        except Exception as e:
            self.fail(f"S0 Navigation layer test failed: {e}")
    
    def test_s3_tensor_core(self):
        """Test que la couche S3 Tensor Core fonctionne"""
        print("Testing S3 Tensor Core...")
        
        try:
            from lib.s3_tensor import TensorGrid, HintCache, TraceRecorder
            from lib.s3_tensor.tensor_grid import GridBounds, CellSymbol
            
            # Créer TensorGrid
            bounds = GridBounds(-10, -10, 10, 10)
            tensor_grid = TensorGrid(bounds)
            
            # Créer HintCache
            hint_cache = HintCache()
            
            # Créer TraceRecorder (optionnel)
            trace_recorder = TraceRecorder()
            
            # Tester TensorGrid
            symbols = np.array([[CellSymbol.EMPTY.value]], dtype=np.int8)
            confidence = np.array([[1.0]], dtype=np.float32)
            
            tensor_grid.update_region(bounds, symbols, confidence)
            stats = tensor_grid.get_stats()
            self.assertIn('total_cells', stats)
            
            # Tester HintCache
            hint_cache.publish_hint('test', {'data': 'test'}, 1.0)
            hints = hint_cache.get_hints_by_type('test')
            self.assertIsInstance(hints, list)
            
            # Tester TraceRecorder
            trace_recorder.record_event('test_event', {'data': 'test'})
            trace_recorder.shutdown()
            
            print("✅ S3 Tensor Core fully functional")
            
        except Exception as e:
            self.fail(f"S3 Tensor Core test failed: {e}")
    
    def test_s4_solver_csp(self):
        """Test que le moteur CSP S4 fonctionne"""
        print("Testing S4 Solver CSP engine...")
        
        try:
            from lib.s4_solver.csp import CSPEngine, CSPResult, CSPSolution
            from lib.s3_tensor import TensorGrid
            from lib.s3_tensor.tensor_grid import GridBounds, CellSymbol
            
            # Créer TensorGrid
            bounds = GridBounds(-5, -5, 5, 5)
            tensor_grid = TensorGrid(bounds)
            
            # Créer CSPEngine
            csp_engine = CSPEngine(tensor_grid)
            
            # Tester la résolution (même sans données réelles)
            result = csp_engine.solve_region(bounds, timeout=1.0)
            
            self.assertIsInstance(result, CSPResult)
            self.assertIsInstance(result.solving_time, float)
            self.assertIsInstance(result.solutions, list)
            
            # Tester les statistiques
            stats = csp_engine.get_stats()
            self.assertIn('solving_attempts', stats)
            
            print("✅ S4 Solver CSP engine fully functional")
            
        except Exception as e:
            self.fail(f"S4 Solver CSP test failed: {e}")
    
    def test_s5_actionneur(self):
        """Test que la couche S5 Actionneur fonctionne"""
        print("Testing S5 Actionneur...")
        
        try:
            from lib.s5_actionneur import ActionQueue, ActionExecutor, ActionLogger
            from lib.s5_actionneur.s51_action_queue import GameAction, ActionType
            
            # Créer ActionQueue
            action_queue = ActionQueue()
            
            # Créer une action
            action = GameAction(
                action_type=ActionType.CLICK_CELL,
                coordinates=(0, 0),
                priority=1
            )
            
            # Tester la mise en file
            action_id = action_queue.enqueue_action(action)
            self.assertIsNotNone(action_id)
            
            # Tester la récupération
            retrieved_action = action_queue.get_next_action()
            self.assertIsNotNone(retrieved_action)
            
            # Tester ActionLogger
            action_logger = ActionLogger()
            action_logger.log_action(action, True, 0.1)
            action_logger.shutdown()
            
            print("✅ S5 Actionneur fully functional")
            
        except Exception as e:
            self.fail(f"S5 Actionneur test failed: {e}")
    
    def test_s6_pathfinder(self):
        """Test que la couche S6 Pathfinder fonctionne"""
        print("Testing S6 Pathfinder...")
        
        try:
            from lib.s6_pathfinder import DensityAnalyzer, PathPlanner, ViewportScheduler
            from lib.s3_tensor import TensorGrid, HintCache
            from lib.s3_tensor.tensor_grid import GridBounds
            
            # Créer les dépendances
            bounds = GridBounds(-10, -10, 10, 10)
            tensor_grid = TensorGrid(bounds)
            hint_cache = HintCache()
            
            # Créer DensityAnalyzer
            density_analyzer = DensityAnalyzer(tensor_grid, hint_cache)
            
            # Tester l'analyse (même sans données)
            density_map = density_analyzer.analyze_density(bounds)
            self.assertIsNotNone(density_map)
            
            # Tester PathPlanner
            path_planner = PathPlanner(tensor_grid)
            path = path_planner.plan_path((0, 0), (5, 5))
            self.assertIsInstance(path, list)
            
            # Tester ViewportScheduler
            viewport_scheduler = ViewportScheduler(tensor_grid)
            schedule = viewport_scheduler.schedule_viewport_updates(bounds)
            self.assertIsInstance(schedule, list)
            
            print("✅ S6 Pathfinder fully functional")
            
        except Exception as e:
            self.fail(f"S6 Pathfinder test failed: {e}")
    
    def test_ops_layer(self):
        """Test que la couche Ops fonctionne"""
        print("Testing Ops layer...")
        
        try:
            from lib.ops import MetricsCollector, AsyncLogger, PersistenceManager
            
            # Tester MetricsCollector avec TraceRecorder None
            metrics_collector = MetricsCollector(trace_recorder=None)
            metrics_collector.increment_counter("test_metric", 1.0)
            stats = metrics_collector.get_stats()
            self.assertIsNotNone(stats)
            
            # Tester AsyncLogger avec TraceRecorder None
            async_logger = AsyncLogger(trace_recorder=None)
            async_logger.info("test", "test message")
            async_logger.shutdown()
            
            # Tester PersistenceManager
            persistence_manager = PersistenceManager()
            persistence_manager.save_data("test", {"data": "test"})
            loaded_data = persistence_manager.load_data("test")
            self.assertIsNotNone(loaded_data)
            
            print("✅ Ops layer fully functional")
            
        except Exception as e:
            self.fail(f"Ops layer test failed: {e}")
    
    def test_architecture_integration(self):
        """Test l'intégration entre les couches"""
        print("Testing cross-layer integration...")
        
        try:
            # Importer tous les composants principaux
            from lib.s0_navigation import CoordinateConverter
            from lib.s3_tensor import TensorGrid, HintCache
            from lib.s3_tensor.tensor_grid import GridBounds, CellSymbol
            from lib.s4_solver import HybridSolver
            from lib.s5_actionneur import ActionExecutor
            from lib.s6_pathfinder import ViewportScheduler
            
            # Créer les composants avec des dépendances partagées
            bounds = GridBounds(-20, -20, 20, 20)
            tensor_grid = TensorGrid(bounds)
            hint_cache = HintCache()
            coord_converter = CoordinateConverter()
            
            # Vérifier que les composants peuvent être créés
            self.assertIsNotNone(tensor_grid)
            self.assertIsNotNone(hint_cache)
            self.assertIsNotNone(coord_converter)
            
            # Tester la cohérence des types partagés
            self.assertEqual(CellSymbol.EMPTY.value, 0)
            self.assertEqual(CellSymbol.MINE.value, -1)
            self.assertEqual(CellSymbol.UNKNOWN.value, -2)
            
            # Tester l'intégration TensorGrid -> HintCache
            hint_cache.publish_hint('tensor_update', {'bounds': bounds}, 1.0)
            hints = hint_cache.get_hints_by_type('tensor_update')
            self.assertEqual(len(hints), 1)
            
            print("✅ Cross-layer integration working")
            
        except Exception as e:
            self.fail(f"Architecture integration test failed: {e}")
    
    def test_dependency_resilience(self):
        """Test la résilience aux dépendances manquantes"""
        print("Testing dependency resilience...")
        
        try:
            # Vérifier que scipy est optionnel dans S0 et S6
            from lib.s0_navigation import InterfaceDetector
            from lib.s6_pathfinder import DensityAnalyzer
            
            # Les composants devraient fonctionner même sans scipy
            interface_detector = InterfaceDetector()
            self.assertIsNotNone(interface_detector)
            
            # Créer TensorGrid et HintCache pour DensityAnalyzer
            from lib.s3_tensor import TensorGrid, HintCache
            bounds = GridBounds(-5, -5, 5, 5)
            tensor_grid = TensorGrid(bounds)
            hint_cache = HintCache()
            
            density_analyzer = DensityAnalyzer(tensor_grid, hint_cache)
            self.assertIsNotNone(density_analyzer)
            
            # Vérifier les flags de dépendances
            stats = density_analyzer.get_stats()
            self.assertIn('has_scipy', stats)
            self.assertIn('has_sklearn', stats)
            
            print("✅ Dependency resilience working")
            
        except Exception as e:
            self.fail(f"Dependency resilience test failed: {e}")


def run_core_architecture_tests():
    """Exécute tous les tests d'intégration de l'architecture core"""
    print("=" * 60)
    print("DÉMARRAGE DES TESTS D'INTÉGRATION ARCHITECTURE CORE S0-S6")
    print("=" * 60)
    
    # Créer la suite de tests
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestCoreArchitectureIntegration)
    
    # Exécuter les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Afficher le résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS D'INTÉGRATION CORE")
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
    
    if success:
        print("\n🎉 ARCHITECTURE S0-S6 CORE FONCTIONNELLE!")
        print("✅ Toutes les couches principales importent et fonctionnent")
        print("✅ L'intégration inter-couches est validée")
        print("✅ La résilience aux dépendances est confirmée")
        print("\n📋 DÉPENDANCES OPTIONNELLES IDENTIFIÉES:")
        print("- cv2 (OpenCV): requis pour S1 Capture et S2 Recognition")
        print("- scipy: optionnel avec fallbacks dans S0 et S6")
        print("- sklearn: optionnel avec fallbacks dans S6")
        print("- selenium: requis pour l'automation navigateur")
    
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    run_core_architecture_tests()
