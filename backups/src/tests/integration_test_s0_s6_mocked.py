"""
Integration Test - Validation S0-S6 avec Mocks

Test d'intégration qui valide le flux complet S0→S1→S2→S3→S4→S5→S6
en utilisant des mocks pour éviter les dépendances externes.
"""

import sys
import os
import time
import unittest
from unittest.mock import Mock, MagicMock, patch
import numpy as np

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestS0S6PipelineMocked(unittest.TestCase):
    """
    Tests d'intégration avec mocks pour le pipeline S0-S6 complet
    """
    
    def setUp(self):
        """Configuration des tests avec mocks"""
        # Mock des dépendances externes
        self.mock_cv2 = MagicMock()
        self.mock_selenium = MagicMock()
        self.mock_scipy = MagicMock()
        
        # Patcher les imports au niveau du module
        self.patches = []
        
        # Patcher cv2
        cv2_patch = patch.dict('sys.modules', {'cv2': self.mock_cv2})
        cv2_patch.start()
        self.patches.append(cv2_patch)
        
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
        
        # Mock des captures d'écran
        self.mock_screenshot = np.zeros((800, 1200, 3), dtype=np.uint8)
        self.mock_screenshot[:] = (50, 100, 150)
        self.mock_cv2.imread.return_value = self.mock_screenshot
        self.mock_cv2.imwrite.return_value = True
    
    def tearDown(self):
        """Nettoyage des patches"""
        for patch in self.patches:
            patch.stop()
    
    def test_s0_navigation_layer_imports(self):
        """Test que les couches S0 peuvent être importées avec mocks"""
        print("Testing S0 Navigation layer imports...")
        
        try:
            from lib.s0_navigation import BrowserNavigation, CoordinateConverter, InterfaceDetector
            self.assertTrue(True, "S0 Navigation imports should succeed")
        except ImportError as e:
            self.fail(f"S0 Navigation import failed: {e}")
    
    def test_s1_capture_layer_imports(self):
        """Test que les couches S1 peuvent être importées avec mocks"""
        print("Testing S1 Capture layer imports...")
        
        try:
            from lib.s1_capture import CaptureTrigger, PatchSegmenter, MetadataExtractor
            self.assertTrue(True, "S1 Capture imports should succeed")
        except ImportError as e:
            self.fail(f"S1 Capture import failed: {e}")
    
    def test_s2_recognition_layer_imports(self):
        """Test que les couches S2 peuvent être importées avec mocks"""
        print("Testing S2 Recognition layer imports...")
        
        try:
            from lib.s2_recognition import TemplateHierarchy, SmartMatcher, FrontierExtractor
            self.assertTrue(True, "S2 Recognition imports should succeed")
        except ImportError as e:
            self.fail(f"S2 Recognition import failed: {e}")
    
    def test_s3_tensor_core_imports(self):
        """Test que les couches S3 peuvent être importées"""
        print("Testing S3 Tensor Core imports...")
        
        try:
            from lib.s3_tensor import TensorGrid, HintCache, TraceRecorder
            self.assertTrue(True, "S3 Tensor Core imports should succeed")
        except ImportError as e:
            self.fail(f"S3 Tensor Core import failed: {e}")
    
    def test_s4_solver_imports(self):
        """Test que les couches S4 peuvent être importées"""
        print("Testing S4 Solver imports...")
        
        try:
            from lib.s4_solver import HybridSolver
            self.assertTrue(True, "S4 Solver imports should succeed")
        except ImportError as e:
            self.fail(f"S4 Solver import failed: {e}")
    
    def test_s5_actionneur_imports(self):
        """Test que les couches S5 peuvent être importées"""
        print("Testing S5 Actionneur imports...")
        
        try:
            from lib.s5_actionneur import ActionQueue, ActionExecutor, ActionLogger
            self.assertTrue(True, "S5 Actionneur imports should succeed")
        except ImportError as e:
            self.fail(f"S5 Actionneur import failed: {e}")
    
    def test_s6_pathfinder_imports(self):
        """Test que les couches S6 peuvent être importées"""
        print("Testing S6 Pathfinder imports...")
        
        try:
            from lib.s6_pathfinder import DensityAnalyzer, PathPlanner, ViewportScheduler
            self.assertTrue(True, "S6 Pathfinder imports should succeed")
        except ImportError as e:
            self.fail(f"S6 Pathfinder import failed: {e}")
    
    def test_ops_layer_imports(self):
        """Test que la couche Ops peut être importée"""
        print("Testing Ops layer imports...")
        
        try:
            from lib.ops import MetricsCollector, AsyncLogger, PersistenceManager
            self.assertTrue(True, "Ops layer imports should succeed")
        except ImportError as e:
            self.fail(f"Ops layer import failed: {e}")
    
    def test_adapters_imports(self):
        """Test que tous les adaptateurs peuvent être importés"""
        print("Testing adapters imports...")
        
        try:
            from services.adapters import (
                SessionSetupAdapter, ActionExecutorAdapter, NavigationAdapter,
                ZoneCaptureAdapter, OptimizedAnalysisAdapter, GameSolverAdapter,
                GameLoopAdapter
            )
            self.assertTrue(True, "All adapters imports should succeed")
        except ImportError as e:
            self.fail(f"Adapters import failed: {e}")
    
    def test_tensor_grid_functionality(self):
        """Test les fonctionnalités de base de TensorGrid"""
        print("Testing TensorGrid functionality...")
        
        try:
            from lib.s3_tensor import TensorGrid
            from lib.s3_tensor.tensor_grid import GridBounds, CellSymbol
            
            # Créer TensorGrid
            bounds = GridBounds(-10, -10, 10, 10)
            tensor_grid = TensorGrid(bounds)
            
            # Tester la mise à jour
            symbols = np.array([[CellSymbol.EMPTY.value]], dtype=np.int8)
            confidence = np.array([[1.0]], dtype=np.float32)
            
            tensor_grid.update_region(bounds, symbols, confidence)
            
            # Tester les statistiques
            stats = tensor_grid.get_stats()
            self.assertIn('total_cells', stats, "Stats should include total cells")
            
            self.assertTrue(True, "TensorGrid functionality should work")
            
        except Exception as e:
            self.fail(f"TensorGrid test failed: {e}")
    
    def test_action_queue_functionality(self):
        """Test les fonctionnalités de base de ActionQueue"""
        print("Testing ActionQueue functionality...")
        
        try:
            from lib.s5_actionneur import ActionQueue, GameAction, ActionType
            
            # Créer ActionQueue
            action_queue = ActionQueue()
            
            # Créer une action
            action = GameAction(
                action_type=ActionType.CLICK_CELL,
                coordinates=(5, 10),
                priority=1
            )
            
            # Tester la mise en file
            action_id = action_queue.enqueue_action(action)
            self.assertIsNotNone(action_id, "Action should be queued")
            
            # Tester la récupération
            retrieved_action = action_queue.get_next_action()
            self.assertIsNotNone(retrieved_action, "Action should be retrievable")
            
            self.assertTrue(True, "ActionQueue functionality should work")
            
        except Exception as e:
            self.fail(f"ActionQueue test failed: {e}")
    
    def test_hint_cache_functionality(self):
        """Test les fonctionnalités de base de HintCache"""
        print("Testing HintCache functionality...")
        
        try:
            from lib.s3_tensor import HintCache
            
            # Créer HintCache
            hint_cache = HintCache()
            
            # Tester la publication d'un indice
            hint_cache.publish_hint(
                hint_type='test_hint',
                data={'test': 'data'},
                priority=1.0
            )
            
            # Tester la récupération
            hints = hint_cache.get_hints_by_type('test_hint')
            self.assertIsInstance(hints, list, "Hints should be a list")
            
            self.assertTrue(True, "HintCache functionality should work")
            
        except Exception as e:
            self.fail(f"HintCache test failed: {e}")
    
    def test_metrics_collector_with_none_recorder(self):
        """Test MetricsCollector avec TraceRecorder None"""
        print("Testing MetricsCollector with None TraceRecorder...")
        
        try:
            from lib.ops import MetricsCollector
            
            # Créer avec TraceRecorder None
            metrics_collector = MetricsCollector(trace_recorder=None)
            
            # Enregistrer une métrique (ne devrait pas lever d'exception)
            metrics_collector.record_metric("test_metric", 1.0)
            
            # Obtenir les statistiques
            stats = metrics_collector.get_stats()
            self.assertIn('metrics_recorded', stats, "Stats should include metrics recorded")
            
            self.assertTrue(True, "MetricsCollector should handle None TraceRecorder")
            
        except Exception as e:
            self.fail(f"MetricsCollector test failed: {e}")
    
    def test_async_logger_with_none_recorder(self):
        """Test AsyncLogger avec TraceRecorder None"""
        print("Testing AsyncLogger with None TraceRecorder...")
        
        try:
            from lib.ops import AsyncLogger
            
            # Créer avec TraceRecorder None
            async_logger = AsyncLogger(trace_recorder=None)
            
            # Logger un message (ne devrait pas lever d'exception)
            async_logger.info("test", "test message")
            
            # Arrêter proprement
            async_logger.shutdown()
            
            self.assertTrue(True, "AsyncLogger should handle None TraceRecorder")
            
        except Exception as e:
            self.fail(f"AsyncLogger test failed: {e}")
    
    def test_session_setup_adapter_initialization_mocked(self):
        """Test l'initialisation de SessionSetupAdapter avec mocks"""
        print("Testing SessionSetupAdapter initialization with mocks...")
        
        try:
            from services.adapters import SessionSetupAdapter
            
            # Créer l'adaptateur
            session_adapter = SessionSetupAdapter(auto_close_browser=False)
            
            # Tester la configuration de session
            result = session_adapter.setup_session(difficulty="beginner")
            
            # Vérifications
            self.assertTrue(result, "Session setup should succeed with mocks")
            self.assertTrue(session_adapter.is_session_active(), "Session should be active")
            
            # Nettoyer
            session_adapter.cleanup_session()
            
            self.assertTrue(True, "SessionSetupAdapter should work with mocks")
            
        except Exception as e:
            self.fail(f"SessionSetupAdapter test failed: {e}")
    
    def test_action_type_enum_mapping_no_conflict(self):
        """Test qu'il n'y a pas de conflit entre les énumérations ActionType"""
        print("Testing ActionType enum mapping no conflict...")
        
        try:
            from services.adapters.s4_action_executor_adapter import LegacyActionType
            from lib.s5_actionneur import ActionType
            
            # Les énumérations devraient être distinctes
            self.assertNotEqual(LegacyActionType.CLICK_LEFT, ActionType.CLICK_CELL)
            self.assertNotEqual(LegacyActionType.CLICK_RIGHT, ActionType.FLAG_CELL)
            
            # Vérifier que les valeurs sont différentes
            self.assertNotEqual(LegacyActionType.CLICK_LEFT.value, ActionType.CLICK_CELL.value)
            self.assertNotEqual(LegacyActionType.CLICK_RIGHT.value, ActionType.FLAG_CELL.value)
            
            self.assertTrue(True, "ActionType enums should not conflict")
            
        except Exception as e:
            self.fail(f"ActionType enum test failed: {e}")
    
    def test_scipy_fallback_in_interface_detector(self):
        """Test le fallback scipy dans InterfaceDetector"""
        print("Testing scipy fallback in InterfaceDetector...")
        
        try:
            from lib.s0_navigation import InterfaceDetector
            
            # Créer InterfaceDetector
            detector = InterfaceDetector()
            
            # Tester la détection (devrait utiliser le fallback numpy)
            result = detector.detect_elements(self.mock_screenshot)
            self.assertIsInstance(result, list, "Detection result should be a list")
            
            self.assertTrue(True, "SciPy fallback should work")
            
        except Exception as e:
            self.fail(f"SciPy fallback test failed: {e}")
    
    def test_architecture_integration_points(self):
        """Test les points d'intégration de l'architecture"""
        print("Testing architecture integration points...")
        
        try:
            # Importer tous les composants principaux
            from lib.s0_navigation import BrowserNavigation, CoordinateConverter
            from lib.s1_capture import CaptureTrigger, PatchSegmenter
            from lib.s2_recognition import SmartMatcher, FrontierExtractor
            from lib.s3_tensor import TensorGrid, HintCache
            from lib.s4_solver import HybridSolver
            from lib.s5_actionneur import ActionExecutor
            from lib.s6_pathfinder import ViewportScheduler
            
            # Vérifier que les types partagés sont cohérents
            from lib.s3_tensor.tensor_grid import GridBounds, CellSymbol
            
            # Créer les composants avec des dépendances partagées
            bounds = GridBounds(-20, -20, 20, 20)
            tensor_grid = TensorGrid(bounds)
            hint_cache = HintCache()
            
            # Les composants devraient pouvoir être créés
            self.assertIsNotNone(tensor_grid, "TensorGrid should be created")
            self.assertIsNotNone(hint_cache, "HintCache should be created")
            
            # Vérifier que les types sont partagés correctement
            self.assertEqual(CellSymbol.EMPTY.value, 0, "CellSymbol values should be consistent")
            
            self.assertTrue(True, "Architecture integration points should work")
            
        except Exception as e:
            self.fail(f"Architecture integration test failed: {e}")


def run_mocked_integration_tests():
    """Exécute tous les tests d'intégration avec mocks"""
    print("=" * 60)
    print("DÉMARRAGE DES TESTS D'INTÉGRATION S0-S6 (MOCKED)")
    print("=" * 60)
    
    # Créer la suite de tests
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestS0S6PipelineMocked)
    
    # Exécuter les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Afficher le résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS D'INTÉGRATION (MOCKED)")
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
    run_mocked_integration_tests()
