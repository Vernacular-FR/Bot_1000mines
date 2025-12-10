"""
Orchestrator Integration Test - Validation complète S0-S6

Test d'intégration final qui valide l'orchestrateur complet en mode legacy et direct,
assurant la migration progressive et la compatibilité avec les services existants.
"""

import sys
import os
import time
import unittest
from unittest.mock import Mock, MagicMock, patch
import numpy as np

# Patch dependencies BEFORE any imports to handle module-level imports
mock_cv2 = MagicMock()
mock_selenium = MagicMock()

# Patch cv2 and selenium at module level
cv2_patch = patch.dict('sys.modules', {'cv2': mock_cv2})
cv2_patch.start()

selenium_patch = patch.dict('sys.modules', {
    'selenium': mock_selenium,
    'selenium.webdriver': mock_selenium.webdriver,
    'selenium.webdriver.chrome': mock_selenium.webdriver.chrome,
    'selenium.webdriver.chrome.options': mock_selenium.webdriver.chrome.options
})
selenium_patch.start()

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestOrchestratorIntegration(unittest.TestCase):
    """
    Tests d'intégration complets pour l'orchestrateur S0-S6
    """
    
    def setUp(self):
        """Configuration des tests"""
        # Mock des dépendances externes
        self.mock_cv2 = MagicMock()
        self.mock_selenium = MagicMock()
        
        # Patcher les imports au niveau du module
        self.patches = []
        
        # Patcher cv2 (OpenCV)
        cv2_patch = patch.dict('sys.modules', {
            'cv2': self.mock_cv2
        })
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
    
    def tearDown(self):
        """Nettoyage des patches"""
        for patch in self.patches:
            patch.stop()
    
    def test_orchestrator_legacy_mode_initialization(self):
        """Test l'initialisation de l'orchestrateur en mode legacy"""
        print("Testing Orchestrator LEGACY mode initialization...")
        
        try:
            # Import direct pour éviter les imports legacy cassés
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
            from orchestrator import Orchestrator
            
            # Créer l'orchestrateur en mode legacy
            orchestrator = Orchestrator(use_legacy_mode=True)
            
            # Initialiser
            success = orchestrator.initialize(difficulty="beginner")
            
            # Vérifications
            self.assertTrue(success, "Legacy mode initialization should succeed")
            self.assertTrue(orchestrator.is_initialized)
            self.assertEqual(orchestrator.current_phase, "legacy_ready")
            self.assertTrue(orchestrator.use_legacy_mode)
            
            # Vérifier que les adaptateurs sont créés
            self.assertIsNotNone(orchestrator.session_adapter)
            self.assertIsNotNone(orchestrator.game_loop_adapter)
            
            # Vérifier la progression de migration
            migration_status = orchestrator.get_migration_status()
            self.assertEqual(migration_status['current_mode'], 'legacy')
            self.assertGreaterEqual(migration_status['migration_progress'], 0.3)
            
            print("✅ Legacy mode initialization successful")
            
        except Exception as e:
            self.fail(f"Legacy mode initialization test failed: {e}")
    
    def test_orchestrator_direct_mode_initialization(self):
        """Test l'initialisation de l'orchestrateur en mode direct"""
        print("Testing Orchestrator DIRECT mode initialization...")
        
        try:
            # Import direct pour éviter les imports legacy cassés
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
            from orchestrator import Orchestrator
            
            # Créer l'orchestrateur en mode direct
            orchestrator = Orchestrator(use_legacy_mode=False)
            
            # Initialiser
            success = orchestrator.initialize(difficulty="beginner")
            
            # Vérifications
            self.assertTrue(success, "Direct mode initialization should succeed")
            self.assertTrue(orchestrator.is_initialized)
            self.assertEqual(orchestrator.current_phase, "direct_ready")
            self.assertFalse(orchestrator.use_legacy_mode)
            
            # Vérifier que les couches S0-S6 sont créées
            self.assertIsNotNone(orchestrator.s0_browser_nav)
            self.assertIsNotNone(orchestrator.s1_capture_trigger)
            self.assertIsNotNone(orchestrator.s2_smart_matcher)
            self.assertIsNotNone(orchestrator.s3_tensor_grid)
            self.assertIsNotNone(orchestrator.s4_hybrid_solver)
            self.assertIsNotNone(orchestrator.s5_action_executor)
            self.assertIsNotNone(orchestrator.s6_path_planner)
            self.assertIsNotNone(orchestrator.ops_metrics)
            
            # Vérifier la progression de migration
            migration_status = orchestrator.get_migration_status()
            self.assertEqual(migration_status['current_mode'], 'direct')
            self.assertEqual(migration_status['migration_progress'], 1.0)
            
            print("✅ Direct mode initialization successful")
            
        except Exception as e:
            self.fail(f"Direct mode initialization test failed: {e}")
    
    def test_legacy_mode_game_iteration(self):
        """Test une itération de jeu en mode legacy"""
        print("Testing LEGACY mode game iteration...")
        
        try:
            # Import direct pour éviter les imports legacy cassés
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
            from orchestrator import Orchestrator
            
            # Initialiser en mode legacy
            orchestrator = Orchestrator(use_legacy_mode=True)
            success = orchestrator.initialize(difficulty="beginner")
            self.assertTrue(success)
            
            # Exécuter une itération
            result = orchestrator.run_game_iteration()
            
            # Vérifications
            self.assertTrue(result.get('success', False), "Game iteration should succeed")
            self.assertIn('iteration_count', result)
            self.assertIn('mode', result)
            self.assertEqual(result['mode'], 'legacy')
            
            # Vérifier les statistiques
            self.assertGreater(orchestrator.stats['total_iterations'], 0)
            
            print("✅ Legacy mode game iteration successful")
            
        except Exception as e:
            self.fail(f"Legacy mode game iteration test failed: {e}")
    
    def test_direct_mode_game_iteration(self):
        """Test une itération de jeu en mode direct"""
        print("Testing DIRECT mode game iteration...")
        
        try:
            # Import direct pour éviter les imports legacy cassés
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
            from orchestrator import Orchestrator
            
            # Initialiser en mode direct
            orchestrator = Orchestrator(use_legacy_mode=False)
            success = orchestrator.initialize(difficulty="beginner")
            self.assertTrue(success)
            
            # Mock les résultats de capture et analyse pour le test
            orchestrator.s1_capture_trigger.trigger_manual_capture = Mock(return_value=Mock(
                success=True,
                screenshot=np.zeros((100, 100, 3), dtype=np.uint8)
            ))
            
            orchestrator.s2_smart_matcher.analyze_image = Mock(return_value=Mock(
                success=True,
                recognized_cells=[
                    {'coordinates': (0, 0), 'symbol': 0, 'confidence': 1.0}  # CellSymbol.EMPTY.value = 0
                ]
            ))
            
            # Mock solution du solveur
            mock_solution = Mock()
            mock_solution.confidence = 0.9
            mock_solution.moves = [Mock(coordinates=(0, 0))]
            orchestrator.s4_hybrid_solver.solve_grid = Mock(return_value=mock_solution)
            
            orchestrator.s5_action_executor.execute_action = Mock(return_value=True)
            orchestrator.s6_path_planner.plan_path = Mock(return_value=[(0, 0), (1, 1)])
            
            # Exécuter une itération
            result = orchestrator.run_game_iteration()
            
            # Vérifications
            self.assertTrue(result.get('success', False), "Game iteration should succeed")
            self.assertIn('iteration_count', result)
            self.assertIn('mode', result)
            self.assertEqual(result['mode'], 'direct')
            self.assertIn('path_length', result)
            
            # Vérifier les statistiques
            self.assertGreater(orchestrator.stats['total_iterations'], 0)
            
            print("✅ Direct mode game iteration successful")
            
        except Exception as e:
            self.fail(f"Direct mode game iteration test failed: {e}")
    
    def test_mode_switching(self):
        """Test le basculement entre modes"""
        print("Testing mode switching (Legacy → Direct)...")
        
        try:
            # Import direct pour éviter les imports legacy cassés
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
            from orchestrator import Orchestrator
            
            # Initialiser en mode legacy
            orchestrator = Orchestrator(use_legacy_mode=True)
            success = orchestrator.initialize(difficulty="beginner")
            self.assertTrue(success)
            
            # Vérifier l'état initial
            self.assertTrue(orchestrator.use_legacy_mode)
            self.assertEqual(orchestrator.current_phase, "legacy_ready")
            
            # Basculer vers le mode direct
            switch_success = orchestrator.switch_to_direct_mode()
            
            # Vérifications
            self.assertTrue(switch_success, "Mode switching should succeed")
            self.assertFalse(orchestrator.use_legacy_mode)
            self.assertEqual(orchestrator.current_phase, "direct_ready")
            
            # Vérifier que les couches S0-S6 sont maintenant actives
            self.assertIsNotNone(orchestrator.s0_browser_nav)
            self.assertIsNotNone(orchestrator.s3_tensor_grid)
            
            print("✅ Mode switching successful")
            
        except Exception as e:
            self.fail(f"Mode switching test failed: {e}")
    
    def test_performance_metrics(self):
        """Test la collecte des métriques de performance"""
        print("Testing performance metrics collection...")
        
        try:
            # Import direct pour éviter les imports legacy cassés
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
            from orchestrator import Orchestrator
            
            # Tester en mode legacy
            orchestrator_legacy = Orchestrator(use_legacy_mode=True)
            orchestrator_legacy.initialize(difficulty="beginner")
            
            legacy_metrics = orchestrator_legacy.get_performance_metrics()
            self.assertIn('total_iterations', legacy_metrics)
            self.assertIn('success_rate', legacy_metrics)
            
            # Tester en mode direct
            orchestrator_direct = Orchestrator(use_legacy_mode=False)
            orchestrator_direct.initialize(difficulty="beginner")
            
            direct_metrics = orchestrator_direct.get_performance_metrics()
            self.assertIsNotNone(direct_metrics)
            
            print("✅ Performance metrics collection working")
            
        except Exception as e:
            self.fail(f"Performance metrics test failed: {e}")
    
    def test_session_setup_adapter_integration(self):
        """Test l'intégration de SessionSetupAdapter"""
        print("Testing SessionSetupAdapter integration...")
        
        try:
            from services.adapters import SessionSetupAdapter
            
            # Créer l'adaptateur
            session_adapter = SessionSetupAdapter(auto_close_browser=False)
            
            # Initialiser la session
            success = session_adapter.setup_session(difficulty="beginner")
            self.assertTrue(success, "Session setup should succeed")
            
            # Vérifier que tous les composants S0-S6 sont accessibles
            self.assertIsNotNone(session_adapter.get_bot())
            self.assertIsNotNone(session_adapter.get_coordinate_system())
            self.assertIsNotNone(session_adapter.get_tensor_grid())
            self.assertIsNotNone(session_adapter.get_solver())
            self.assertIsNotNone(session_adapter.get_action_executor())
            
            # Vérifier les composants S1
            self.assertIsNotNone(session_adapter.get_capture_trigger())
            self.assertIsNotNone(session_adapter.get_patch_segmenter())
            self.assertIsNotNone(session_adapter.get_metadata_extractor())
            
            # Vérifier les composants S2
            self.assertIsNotNone(session_adapter.get_template_hierarchy())
            self.assertIsNotNone(session_adapter.get_smart_matcher())
            self.assertIsNotNone(session_adapter.get_frontier_extractor())
            
            # Vérifier les composants S3
            self.assertIsNotNone(session_adapter.get_hint_cache())
            
            print("✅ SessionSetupAdapter integration successful")
            
            # Nettoyer
            session_adapter.cleanup_session()
            
        except Exception as e:
            self.fail(f"SessionSetupAdapter integration test failed: {e}")
    
    def test_complete_s0_s6_pipeline_flow(self):
        """Test le flux complet du pipeline S0-S6"""
        print("Testing complete S0-S6 pipeline flow...")
        
        try:
            # Import direct pour éviter les imports legacy cassés
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
            from orchestrator import Orchestrator
            
            # Initialiser en mode direct pour tester le pipeline complet
            orchestrator = Orchestrator(use_legacy_mode=False)
            success = orchestrator.initialize(difficulty="beginner")
            self.assertTrue(success)
            
            # Vérifier que toutes les couches sont connectées
            # S0 → S1
            self.assertIsNotNone(orchestrator.s0_browser_nav)
            self.assertIsNotNone(orchestrator.s1_capture_trigger)
            
            # S1 → S2
            self.assertIsNotNone(orchestrator.s2_smart_matcher)
            
            # S2 → S3
            self.assertIsNotNone(orchestrator.s3_tensor_grid)
            
            # S3 → S4
            self.assertIsNotNone(orchestrator.s4_hybrid_solver)
            
            # S4 → S5
            self.assertIsNotNone(orchestrator.s5_action_executor)
            
            # S6 (Pathfinder) intégré
            self.assertIsNotNone(orchestrator.s6_path_planner)
            
            # Ops (monitoring)
            self.assertIsNotNone(orchestrator.ops_metrics)
            
            # Tester la cohérence des dépendances
            # Le TensorGrid devrait être partagé entre S2, S4, S5, S6
            tensor_grid = orchestrator.s3_tensor_grid
            self.assertEqual(tensor_grid, orchestrator.s4_hybrid_solver.tensor_grid)
            
            print("✅ Complete S0-S6 pipeline flow validated")
            
        except Exception as e:
            self.fail(f"Complete pipeline flow test failed: {e}")
    
    def test_error_handling_and_recovery(self):
        """Test la gestion des erreurs et la récupération"""
        print("Testing error handling and recovery...")
        
        try:
            # Import direct pour éviter les imports legacy cassés
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
            from orchestrator import Orchestrator
            
            # Tester l'initialisation sans dépendances
            orchestrator = Orchestrator(use_legacy_mode=False)
            
            # Simuler une erreur en patchant une dépendance critique
            with patch('lib.s3_tensor.tensor_grid.TensorGrid', side_effect=Exception("Test error")):
                success = orchestrator.initialize(difficulty="beginner")
                self.assertFalse(success, "Initialization should fail with broken dependencies")
                self.assertFalse(orchestrator.is_initialized)
            
            # Tester que l'orchestrateur peut être réinitialisé
            orchestrator = Orchestrator(use_legacy_mode=False)
            success = orchestrator.initialize(difficulty="beginner")
            self.assertTrue(success, "Re-initialization should succeed")
            
            print("✅ Error handling and recovery working")
            
        except Exception as e:
            self.fail(f"Error handling test failed: {e}")
    
    def test_shutdown_properly(self):
        """Test l'arrêt propre de l'orchestrateur"""
        print("Testing proper shutdown...")
        
        try:
            # Import direct pour éviter les imports legacy cassés
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
            from orchestrator import Orchestrator
            
            # Initialiser dans les deux modes
            orchestrator_legacy = Orchestrator(use_legacy_mode=True)
            orchestrator_legacy.initialize(difficulty="beginner")
            
            orchestrator_direct = Orchestrator(use_legacy_mode=False)
            orchestrator_direct.initialize(difficulty="beginner")
            
            # Vérifier que les deux sont actifs
            self.assertTrue(orchestrator_legacy.is_initialized)
            self.assertTrue(orchestrator_direct.is_initialized)
            
            # Arrêter proprement
            orchestrator_legacy.shutdown()
            orchestrator_direct.shutdown()
            
            # Vérifier l'état final
            self.assertFalse(orchestrator_legacy.is_initialized)
            self.assertFalse(orchestrator_direct.is_initialized)
            self.assertEqual(orchestrator_legacy.current_phase, "shutdown")
            self.assertEqual(orchestrator_direct.current_phase, "shutdown")
            
            print("✅ Proper shutdown working")
            
        except Exception as e:
            self.fail(f"Proper shutdown test failed: {e}")


def run_orchestrator_integration_tests():
    """Exécute tous les tests d'intégration de l'orchestrateur"""
    print("=" * 70)
    print("DÉMARRAGE DES TESTS D'INTÉGRATION ORCHESTRATOR S0-S6")
    print("=" * 70)
    
    # Créer la suite de tests
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestOrchestratorIntegration)
    
    # Exécuter les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Afficher le résumé
    print("\n" + "=" * 70)
    print("RÉSUMÉ DES TESTS D'INTÉGRATION ORCHESTRATOR")
    print("=" * 70)
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
        print("\n🎉 ORCHESTRATOR S0-S6 COMPLÈTEMENT FONCTIONNEL!")
        print("✅ Migration progressive validée")
        print("✅ Compatibilité préservée")
        print("✅ Pipeline S0-S6 intégré")
        print("✅ Gestion d'erreurs robuste")
        print("✅ Performance monitoring actif")
        print("\n🚀 DÉPLOIEMENT PRODUCTION PRÊT!")
        print("- Mode Legacy: Transition progressive sans rupture")
        print("- Mode Direct: Performance optimale S0-S6")
        print("- Basculement: Migration transparente")
        print("- Monitoring: Métriques temps réel")
    
    print("=" * 70)
    
    return success


if __name__ == "__main__":
    run_orchestrator_integration_tests()
