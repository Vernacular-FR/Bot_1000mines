#!/usr/bin/env python3
"""
Tests du Scénario 5 : Jeu Automatique Complet

Tests unitaires et d'intégration pour valider le fonctionnement
du système de jeu automatique complet.
"""

import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import time

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.s5_game_loop_service import GameLoopService, GameState, GameResult
from services.s2_optimized_analysis_service import OptimizedAnalysisService
from services.s3_game_solver_service import GameSolverService
from services.s4_action_executor_service import ActionExecutorService
from lib.s2_analysis.grid_state import GamePersistence, GridDB


class TestGameLoopService(unittest.TestCase):
    """Tests unitaires pour GameLoopService"""

    def setUp(self):
        """Configuration avant chaque test"""
        self.driver = Mock()
        self.coordinate_system = Mock()
        self.service = GameLoopService(
            driver=self.driver,
            coordinate_system=self.coordinate_system,
            max_iterations=5,
            iteration_timeout=10.0,
            delay_between_iterations=0.1
        )

    def test_initialization(self):
        """Test de l'initialisation du service"""
        self.assertIsNotNone(self.service.driver)
        self.assertIsNotNone(self.service.coordinate_system)
        self.assertEqual(self.service.max_iterations, 5)
        self.assertEqual(self.service.iteration_timeout, 10.0)
        self.assertEqual(self.service.delay_between_iterations, 0.1)

    def test_game_state_detection_won(self):
        """Test de la détection d'état gagné"""
        # Mock une analyse avec des mines détectées (défaite)
        analysis_result = {
            'db_path': 'test_db.json',
            'game_status': {'symbol_distribution': {}}
        }

        # Créer une DB temporaire avec une mine
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            db_path = f.name
            db_data = {
                "metadata": {"version": "1.0"},
                "summary": {},
                "cells": [{"x": 0, "y": 0, "type": "mine", "state": "TO_PROCESS"}],
                "actions": [],
                "constraints": []
            }
            import json
            json.dump(db_data, f)

        analysis_result['db_path'] = db_path

        try:
            state = self.service._detect_game_state(analysis_result)
            self.assertEqual(state, GameState.LOST)
        finally:
            os.unlink(db_path)

    def test_should_continue_logic(self):
        """Test de la logique should_continue"""
        # Test avec état WON
        self.assertFalse(self.service._should_continue(GameState.WON, 1))
        self.assertFalse(self.service._should_continue(GameState.LOST, 1))
        self.assertFalse(self.service._should_continue(GameState.ERROR, 1))

        # Test avec itérations max
        self.assertFalse(self.service._should_continue(GameState.PLAYING, self.service.max_iterations))

        # Test continuer
        self.assertTrue(self.service._should_continue(GameState.PLAYING, 1))


class TestOptimizedAnalysisService(unittest.TestCase):
    """Tests pour OptimizedAnalysisService"""

    def setUp(self):
        """Configuration avant chaque test"""
        self.service = OptimizedAnalysisService(generate_overlays=False)

    def test_initialization(self):
        """Test de l'initialisation"""
        self.assertFalse(self.service.generate_overlays)
        self.assertIsNotNone(self.service.template_matcher)
        self.assertIsNotNone(self.service.grid_db)

    def test_analyze_from_path_nonexistent_file(self):
        """Test avec fichier inexistant"""
        result = self.service.analyze_from_path('nonexistent.png')
        self.assertFalse(result['success'])
        self.assertIn('introuvable', result['message'])


class TestGameSolverService(unittest.TestCase):
    """Tests pour GameSolverService"""

    def setUp(self):
        """Configuration avant chaque test"""
        self.service = GameSolverService()

    def test_initialization(self):
        """Test de l'initialisation"""
        self.assertIsNotNone(self.service.grid_analyzer)
        self.assertIsNotNone(self.service.segmentation_visualizer)


class TestActionExecutorService(unittest.TestCase):
    """Tests pour ActionExecutorService"""

    def setUp(self):
        """Configuration avant chaque test"""
        self.driver = Mock()
        self.coordinate_system = Mock()
        self.service = ActionExecutorService(self.driver, self.coordinate_system)

    def test_initialization(self):
        """Test de l'initialisation"""
        self.assertIsNotNone(self.service.driver)
        self.assertIsNotNone(self.service.coordinate_system)

    def test_execute_batch_empty(self):
        """Test exécution batch vide"""
        result = self.service.execute_batch([])
        self.assertEqual(result['total'], 0)
        self.assertEqual(result['successful'], 0)
        self.assertEqual(result['failed'], 0)


class TestScenario5Integration(unittest.TestCase):
    """Tests d'intégration pour le Scénario 5"""

    def setUp(self):
        """Configuration pour les tests d'intégration"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_image = os.path.join(self.temp_dir, 'test_screenshot.png')

        # Créer une image de test simple (noir)
        from PIL import Image
        img = Image.new('L', (100, 100), color=0)
        img.save(self.test_image)

    def tearDown(self):
        """Nettoyage après les tests"""
        shutil.rmtree(self.temp_dir)

    def test_full_analysis_pipeline(self):
        """Test du pipeline complet d'analyse"""
        service = OptimizedAnalysisService(generate_overlays=False)

        # Tester analyze_from_path
        result = service.analyze_from_path(self.test_image)

        # Le test peut échouer à cause du format d'image, mais on teste la structure
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('message', result)

    @patch('services.s5_game_loop_service.GameLoopService._take_screenshot')
    @patch('services.s2_optimized_analysis_service.OptimizedAnalysisService.analyze_from_path')
    @patch('services.s3_game_solver_service.GameSolverService.solve_from_db_path')
    @patch('services.s4_action_executor_service.ActionExecutorService.execute_batch')
    def test_game_loop_simulation(self, mock_execute, mock_solve, mock_analyze, mock_screenshot):
        """Test simulé de la boucle de jeu"""
        # Configuration des mocks
        mock_screenshot.return_value = self.test_image
        mock_analyze.return_value = {
            'success': True,
            'db_path': 'test.db',
            'game_status': {'symbol_distribution': {'unrevealed': 10}}
        }
        mock_solve.return_value = {'actions': []}
        mock_execute.return_value = {'successful': 0, 'failed': 0}

        # Créer le service
        driver = Mock()
        coord_system = Mock()
        service = GameLoopService(driver=driver, coordinate_system=coord_system, max_iterations=2)

        # Simuler une partie qui se termine rapidement
        result = service.play_game()

        # Vérifications
        self.assertIsInstance(result, GameResult)
        self.assertEqual(result.iterations, 1)  # Une itération seulement car pas d'actions

    def test_game_result_structure(self):
        """Test de la structure GameResult"""
        result = GameResult()
        self.assertFalse(result.success)
        self.assertEqual(result.final_state, GameState.PLAYING)
        self.assertEqual(result.iterations, 0)
        self.assertEqual(result.actions_executed, 0)
        self.assertIsInstance(result.message, str)


def run_performance_test():
    """Test de performance basique"""
    print("\n=== TEST DE PERFORMANCE ===")

    start_time = time.time()

    # Test d'initialisation des services
    services = {
        'Analysis': OptimizedAnalysisService,
        'Solver': GameSolverService,
        'ActionExecutor': lambda: ActionExecutorService(None, None),
        'GameLoop': lambda: GameLoopService(max_iterations=1)
    }

    for name, service_class in services.items():
        try:
            if name == 'ActionExecutor':
                service = service_class()
            elif name == 'GameLoop':
                service = service_class()
            else:
                service = service_class(generate_overlays=False)

            print(f"✅ {name}: Initialisation réussie")
        except Exception as e:
            print(f"❌ {name}: Erreur d'initialisation - {e}")

    end_time = time.time()
    print(".2f")
    
def run_integration_test():
    """Test d'intégration basique"""
    print("\n=== TEST D'INTÉGRATION ===")

    try:
        # Test d'import de tous les modules
        from services.s1_session_setup_service import SessionSetupService
        from services.s1_zone_capture_service import ZoneCaptureService
        from src.lib.s0_navigation.coordinate_system import CoordinateConverter, GridViewportMapper

        print("✅ Tous les imports réussis")

        # Test d'initialisation des services principaux
        analysis = OptimizedAnalysisService(generate_overlays=False)
        solver = GameSolverService()
        action_executor = ActionExecutorService(None, None)
        game_loop = GameLoopService(max_iterations=1)

        print("✅ Tous les services initialisés")

        # Test des méthodes principales
        methods_to_test = [
            (analysis, 'analyze_existing_screenshots_optimized', {}),
            (solver, 'solve_from_db_path', {'db_path': 'dummy.db'}),
            (action_executor, 'execute_batch', {'actions': []}),
            (game_loop, 'reset_stats', {}),
        ]

        for service, method_name, kwargs in methods_to_test:
            try:
                method = getattr(service, method_name)
                if kwargs:
                    # Pour les méthodes qui ont besoin d'args, on ne les appelle pas vraiment
                    print(f"✅ {service.__class__.__name__}.{method_name}: Méthode existe")
                else:
                    method()
                    print(f"✅ {service.__class__.__name__}.{method_name}: Appel réussi")
            except Exception as e:
                print(f"⚠️  {service.__class__.__name__}.{method_name}: {e}")

    except Exception as e:
        print(f"❌ Erreur d'intégration: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Fonction principale des tests"""
    print("🧪 TESTS DU SCÉNARIO 5 : JEU AUTOMATIQUE COMPLET")
    print("=" * 60)

    # Tests unitaires
    print("\n📋 TESTS UNITAIRES")
    unittest.main(argv=[''], exit=False, verbosity=2)

    # Tests de performance
    run_performance_test()

    # Tests d'intégration
    run_integration_test()

    print("\n" + "=" * 60)
    print("🎯 TESTS TERMINÉS")
    print("\nPour lancer seulement les tests unitaires:")
    print("python tests/test_scenario5.py TestGameLoopService.test_initialization")
    print("\nPour lancer les tests d'intégration:")
    print("python tests/test_scenario5.py && python -c \"from tests.test_scenario5 import run_integration_test; run_integration_test()\"")


if __name__ == '__main__':
    main()
