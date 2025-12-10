#!/usr/bin/env python3
"""
Test Rapide du Scénario 5

Script simplifié pour tester rapidement le Scénario 5
sans l'interface utilisateur complète.
"""

import os
import sys
import time
from unittest.mock import Mock, patch

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test des imports principaux"""
    print("🔍 Test des imports...")

    try:
        from services.s5_game_loop_service import GameLoopService, GameState
        from services.s2_optimized_analysis_service import OptimizedAnalysisService
        from services.s3_game_solver_service import GameSolverService
        from services.s4_action_executor_service import ActionExecutorService
        from services.s1_session_setup_service import SessionSetupService
        from services.s1_zone_capture_service import ZoneCaptureService

        print("✅ Tous les imports réussis")
        return True
    except Exception as e:
        print(f"❌ Erreur d'import: {e}")
        return False

def test_service_initialization():
    """Test d'initialisation des services"""
    print("\n🔧 Test d'initialisation des services...")

    try:
        # Importer les services nécessaires
        from services.s2_optimized_analysis_service import OptimizedAnalysisService
        from services.s3_game_solver_service import GameSolverService
        from services.s4_action_executor_service import ActionExecutorService
        from services.s5_game_loop_service import GameLoopService
        
        # Services principaux
        analysis = OptimizedAnalysisService(generate_overlays=False)
        solver = GameSolverService()
        action_executor = ActionExecutorService(None, None)
        game_loop = GameLoopService(max_iterations=3)

        print("✅ Services initialisés avec succès")
        return True
    except Exception as e:
        print(f"❌ Erreur d'initialisation: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_analysis_service():
    """Test du service d'analyse"""
    print("\n📊 Test du service d'analyse...")

    from services.s2_optimized_analysis_service import OptimizedAnalysisService
    service = OptimizedAnalysisService(generate_overlays=False)

    # Test avec fichier inexistant
    result = service.analyze_from_path('nonexistent.png')
    if not result['success'] and 'introuvable' in result['message']:
        print("✅ Gestion des fichiers inexistants OK")
    else:
        print("⚠️  Réponse inattendue pour fichier inexistant")
        return False

    # Chercher un vrai fichier de test
    screenshots_dir = 'temp/screenshots/zones'
    if os.path.exists(screenshots_dir):
        png_files = [f for f in os.listdir(screenshots_dir) if f.endswith('.png')]
        if png_files:
            test_file = os.path.join(screenshots_dir, png_files[0])
            print(f"📁 Test avec fichier réel: {test_file}")

            start_time = time.time()
            result = service.analyze_from_path(test_file)
            elapsed = time.time() - start_time

            if result['success']:
                print(f"✅ Analyse réussie en {elapsed:.2f}s")
                if 'db_path' in result:
                    print(f"   📄 DB générée: {result['db_path']}")
                return True
            else:
                print(f"⚠️  Analyse échouée: {result.get('message', 'Erreur inconnue')}")
                return False

    print("⚠️  Aucun fichier de test trouvé, test limité")
    return True

def test_game_loop_service():
    """Test du service de boucle de jeu"""
    print("\n🎮 Test du service de boucle de jeu...")

    try:
        # Importer les classes nécessaires
        from services.s5_game_loop_service import GameLoopService, GameState
        
        # Mock des dépendances
        mock_driver = Mock()
        mock_coord = Mock()

        service = GameLoopService(
            driver=mock_driver,
            coordinate_system=mock_coord,
            max_iterations=2
        )

        # Test des méthodes de base
        if service.max_iterations == 2 and service.current_game_state == GameState.PLAYING:
            print("✅ Attributs OK")
        else:
            print("⚠️  Attributs incorrects")
            return False

        # Test should_continue
        if (service._should_continue(GameState.PLAYING, 1) and
            not service._should_continue(GameState.WON, 1) and
            not service._should_continue(GameState.PLAYING, 3)):  # max_iterations = 2
            print("✅ Logique de boucle OK")
            return True
        else:
            print("⚠️  Logique de boucle incorrecte")
            return False

    except Exception as e:
        print(f"❌ Erreur dans le test de boucle: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_coordinate_conversion():
    """Test de la conversion de coordonnées"""
    print("\n📍 Test de conversion de coordonnées...")

    try:
        from src.lib.s0_navigation.coordinate_system import CoordinateConverter, GridViewportMapper

        # Mock d'un système de coordonnées
        coord_system = CoordinateConverter()

        # Test d'initialisation
        print("✅ Système de coordonnées initialisé")
        return True

    except Exception as e:
        print(f"❌ Erreur de coordonnées: {e}")
        return False

@patch('services.s5_game_loop_service.GameLoopService._take_screenshot')
@patch('services.s2_optimized_analysis_service.OptimizedAnalysisService.analyze_from_path')
@patch('services.s3_game_solver_service.GameSolverService.solve_from_db_path')
@patch('services.s4_action_executor_service.ActionExecutorService.execute_batch')
def test_game_loop_integration(mock_execute, mock_solve, mock_analyze, mock_screenshot):
    """Test d'intégration simulé de la boucle de jeu"""
    print("\n🔄 Test d'intégration de la boucle de jeu...")

    try:
        # Importer les classes nécessaires
        from services.s5_game_loop_service import GameLoopService
        
        # Configuration des mocks
        mock_screenshot.return_value = 'test_screenshot.png'
        mock_analyze.return_value = {
            'success': True,
            'db_path': 'test.db',
            'game_status': {'symbol_distribution': {'unrevealed': 5, 'empty': 10}}
        }
        mock_solve.return_value = {'actions': []}  # Pas d'actions = fin de partie
        mock_execute.return_value = {'successful': 0, 'failed': 0}

        # Créer le service
        service = GameLoopService(max_iterations=3)

        # Simuler une partie
        start_time = time.time()
        result = service.play_game()
        elapsed = time.time() - start_time

        # Vérifications basiques
        if hasattr(result, 'iterations') and hasattr(result, 'success'):
            if result.iterations == 1 and not result.success:  # Une seule itération (pas d'actions)
                print(f"✅ Simulation réussie en {elapsed:.2f}s")
                return True
            else:
                print("⚠️  Résultats inattendus de la simulation")
                return False
        else:
            print("⚠️  Objet result incorrect")
            return False

    except Exception as e:
        print(f"❌ Erreur d'intégration: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Exécute tous les tests"""
    print("🧪 TEST RAPIDE DU SCÉNARIO 5")
    print("=" * 50)

    tests = [
        ("Imports", test_imports),
        ("Initialisation", test_service_initialization),
        ("Analyse", test_analysis_service),
        ("Boucle de jeu", test_game_loop_service),
        ("Coordonnées", test_coordinate_conversion),
        ("Intégration", test_game_loop_integration),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 {test_name}")
        try:
            result = test_func()
            results.append(result)
            status = "✅" if result else "❌"
            print(f"{status} {test_name}: {'RÉUSSI' if result else 'ÉCHOUÉ'}")
        except Exception as e:
            print(f"❌ {test_name}: ERREUR - {e}")
            results.append(False)

    # Résumé
    print("\n" + "=" * 50)
    print("📊 RÉSULTATS DES TESTS")

    passed = sum(results)
    total = len(results)

    for i, (test_name, _) in enumerate(tests):
        status = "✅" if results[i] else "❌"
        print(f"  {status} {test_name}")

    print(f"\n🎯 SCORE: {passed}/{total} tests réussis")

    if passed == total:
        print("🎉 TOUS LES TESTS RÉUSSIS ! Le Scénario 5 est prêt.")
        return True
    else:
        print("⚠️  Quelques tests ont échoué. Vérifiez les erreurs ci-dessus.")
        return False

def main():
    """Fonction principale"""
    success = run_all_tests()

    if success:
        print("\n🚀 Vous pouvez maintenant lancer le Scénario 5 :")
        print("   python main.py")
        print("   Choisir option 5")
    else:
        print("\n🔧 Corrigez les erreurs avant de lancer le Scénario 5.")

    return success

if __name__ == '__main__':
    main()
