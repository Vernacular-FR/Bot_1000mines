#!/usr/bin/env python3
"""
GameSolverService - Service de résolution de jeu avec le solveur CSP hybride

Ce service orchestre la résolution complète d'une grille de démineur :
1. Analyse la GridDB remplie
2. Lance le solveur hybride CSP
3. Génère l'overlay final avec les actions recommandées
"""

from .s4_action_executor_service import GameAction, ActionType

import os
import time
from typing import Dict, Any, Optional, List, Tuple

from lib.config import PATHS
from lib.s2_analysis.grid_state import GamePersistence, GridDB
from lib.s3_solver.cell_analyzer import CellAnalyzer
from lib.s3_solver.core.grid_analyzer import GridAnalyzer
from lib.s3_solver.hybrid_solver import HybridSolver
from lib.s3_solver.visualization.solver_overlay_generator import SolverOverlayGenerator
from lib.s3_solver.visualization.segmentation_visualizer import SegmentationVisualizer


class GameSolverService:
    """Service complet de résolution de jeu de démineur"""

    def __init__(self, generate_overlays: bool = True, paths: Dict[str, str] = None):
        """
        Initialise le service de résolution

        Args:
            generate_overlays: Générer les overlays de solution
            paths: Chemins personnalisés pour les fichiers (obligatoire)
        """
        self.generate_overlays = generate_overlays
        self.overlay_generator = None  # Sera initialisé avec les bons chemins
        self.segmentation_visualizer = None  # Sera initialisé avec les bons chemins

        # Chemins obligatoires - plus de valeurs par défaut
        if not paths:
            raise ValueError("paths est obligatoire pour GameSolverService")
        self.paths = paths
        self.db_path = self.paths.get("grid_db")
        self.solver_overlays_path = self.paths.get("solver")
        
        if not self.db_path or not self.solver_overlays_path:
            raise ValueError("grid_db et solver sont obligatoires dans paths")
        
        # Initialiser les services avec les chemins validés
        if generate_overlays:
            self.overlay_generator = SolverOverlayGenerator(output_dir=self.solver_overlays_path)
            self.segmentation_visualizer = SegmentationVisualizer(output_dir=self.solver_overlays_path)

        print("[INFO] GameSolverService initialisé")

    def solve_from_db_path(self, db_path: Optional[str] = None,
                          screenshot_path: Optional[str] = None,
                          game_id: str = None, iteration_num: int = None) -> Dict[str, Any]:
        """
        Résoudre une grille à partir d'une base de données existante

        Args:
            db_path: Chemin vers la GridDB (optionnel, utilise la valeur par défaut)
            screenshot_path: Chemin vers le screenshot original pour l'overlay

        Returns:
            Dict avec les résultats de la résolution
        """
        start_time = time.time()

        db_path = db_path or self.db_path
        if not db_path:
            return {
                'success': False,
                'message': "Aucun chemin de base de données fourni à GameSolverService",
                'performance': {'total_time': time.time() - start_time}
            }

        if not os.path.exists(db_path):
            return {
                'success': False,
                'message': f"Base de données introuvable: {db_path}",
                'performance': {'total_time': time.time() - start_time}
            }

        try:
            print(f"[SOLVE] Résolution à partir de: {db_path}")

            # 1. Charger la DB
            grid_db = GridDB(db_path)

            # 2. Initialiser l'analyzer et le solveur
            analyzer = GridAnalyzer(grid_db)
            solver = HybridSolver(analyzer)

            # Générer l'overlay de segmentation (intermédiaire)
            segmentation_overlay_path = None
            if self.generate_overlays:
                if not screenshot_path:
                    raise ValueError("screenshot_path est obligatoire lorsque les overlays sont activés")
                if not game_id or iteration_num is None:
                    raise ValueError("game_id et iteration_num sont obligatoires pour générer les overlays")
            if self.generate_overlays and self.segmentation_visualizer:
                try:
                    print("[OVERLAY] Génération de l'overlay de segmentation...")
                    segmentation_overlay_path = self.segmentation_visualizer.visualize(
                        analyzer, solver.segmentation, screenshot_path, game_id, iteration_num
                    )
                except Exception as e:
                    print(f"[WARN] Erreur overlay segmentation: {e}")

            # 3. Résoudre
            print("[SOLVE] Lancement du solveur hybride CSP...")
            solve_start = time.time()
            solver.solve()
            solve_duration = time.time() - solve_start

            # 4. Sauvegarder les résultats dans la DB
            solver.save_to_db(grid_db)
            grid_db.flush_to_disk()

            # 5. Collecter les statistiques
            safe_cells = solver.get_safe_cells()
            flag_cells = solver.get_flag_cells()
            total_cells = len(safe_cells) + len(flag_cells)

            # 6. Générer l'overlay si demandé
            overlay_path = None
            if self.generate_overlays:
                print("[OVERLAY] Génération de l'overlay final...")
                overlay_path = self.overlay_generator.generate_overlay_from_db(
                    screenshot_path, grid_db, game_id, iteration_num
                )

            # 7. Résumé des probabilités pour debug
            prob_summary = {}
            for zone_id, prob in solver.zone_probabilities.items():
                zone = next((z for z in solver.segmentation.zones if z.id == zone_id), None)
                if zone:
                    prob_summary[zone_id] = {
                        'probability': prob,
                        'size': len(zone.cells)
                    }

            return {
                'success': True,
                'message': 'Résolution terminée avec succès',
                'statistics': {
                    'safe_cells': len(safe_cells),
                    'flag_cells': len(flag_cells),
                    'total_actions': total_cells,
                    'zones_analyzed': len(solver.segmentation.zones),
                    'components_solved': len(solver.segmentation.components),
                    'probability_summary': prob_summary
                },
                'actions': {
                    'safe': [(x, y) for x, y in safe_cells],
                    'flag': [(x, y) for x, y in flag_cells]
                },
                'performance': {
                    'total_time': time.time() - start_time,
                    'solve_time': solve_duration,
                    'cells_per_second': total_cells / solve_duration if solve_duration > 0 else 0
                },
                'overlay_path': overlay_path,
                'segmentation_overlay_path': segmentation_overlay_path
            }

        except Exception as e:
            import traceback
            error_msg = f"Erreur lors de la résolution: {str(e)}"
            print(f"[ERREUR] {error_msg}")
            traceback.print_exc()

            return {
                'success': False,
                'message': error_msg,
                'performance': {'total_time': time.time() - start_time}
            }

    def solve_from_screenshot_analysis(self, screenshot_path: str,
                                     analysis_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Pipeline complet : analyse + résolution à partir d'un screenshot

        Args:
            screenshot_path: Chemin vers le screenshot à analyser
            analysis_result: Résultat d'analyse précalculé (optionnel)

        Returns:
            Dict avec analyse + résolution
        """
        start_time = time.time()

        try:
            print(f"[PIPELINE] Pipeline complet pour: {os.path.basename(screenshot_path)}")

            # 1. Analyse si pas déjà faite
            if not analysis_result:
                print("[ANALYSE] Analyse du screenshot...")
                analyzer = CellAnalyzer()
                cells = analyzer.analyze_screenshot(screenshot_path)

                if not cells:
                    return {
                        'success': False,
                        'message': 'Échec de l\'analyse du screenshot',
                        'performance': {'total_time': time.time() - start_time}
                    }

                # Peupler la DB
                db_path = self.db_path
                grid_db = GridDB(db_path)
                grid_db.clear_all()

                for cell in cells:
                    grid_db.add_cell(cell["x"], cell["y"], {
                        "type": cell["type"],
                        "confidence": cell["confidence"],
                        "state": "TO_PROCESS"
                    })

                grid_db.flush_to_disk()
                print(f"[ANALYSE] {len(cells)} cellules analysées et sauvegardées")

                analysis_result = {
                    'cell_count': len(cells),
                    'db_path': db_path
                }
            else:
                print("[ANALYSE] Utilisation de l'analyse précalculée")

            # 2. Résoudre directement ici pour éviter la double génération d'overlays
            print(f"[SOLVE] Résolution à partir de: {analysis_result.get('db_path')}")
            
            # Charger la DB et résoudre
            grid_db = GridDB(analysis_result.get('db_path'))
            analyzer = GridAnalyzer(grid_db)
            solver = HybridSolver(analyzer)
            
            solve_start = time.time()
            solver.solve()
            solve_duration = time.time() - solve_start
            
            # Collecter les résultats
            safe_cells = solver.get_safe_cells()
            flag_cells = solver.get_flag_cells()
            
            solve_result = {
                'success': True,
                'safe_cells': [(c.x, c.y) for c in safe_cells],
                'flag_cells': [(c.x, c.y) for c in flag_cells],
                'total_actions': len(safe_cells) + len(flag_cells),
                'solver_stats': {
                    'solve_duration': solve_duration
                }
            }

            # 3. Combiner les résultats
            combined_result = {
                'success': solve_result['success'],
                'message': solve_result.get('message', 'Pipeline terminé'),
                'analysis': {
                    'cell_count': analysis_result.get('cell_count', 0),
                    'screenshot_path': screenshot_path
                },
                'solving': solve_result,
                'performance': {
                    'total_time': time.time() - start_time,
                    'analysis_time': solve_result.get('performance', {}).get('total_time', 0),
                    'solve_time': solve_result.get('performance', {}).get('solve_time', 0)
                }
            }

            if solve_result.get('overlay_path'):
                combined_result['overlay_path'] = solve_result['overlay_path']

            return combined_result

        except Exception as e:
            import traceback
            error_msg = f"Erreur dans le pipeline complet: {str(e)}"
            print(f"[ERREUR] {error_msg}")
            traceback.print_exc()

            return {
                'success': False,
                'message': error_msg,
                'performance': {'total_time': time.time() - start_time}
            }

    def get_game_status_from_db(self, db_path: Optional[str] = None) -> Dict[str, Any]:
        """
        État du jeu à partir de la DB (pour debug/monitoring)

        Args:
            db_path: Chemin vers la DB

        Returns:
            Dict avec l'état du jeu
        """
        db_path = db_path or self.db_path

        if not os.path.exists(db_path):
            return {'success': False, 'message': 'DB introuvable'}

        try:
            grid_db = GridDB(db_path)
            summary = grid_db.get_summary()

            return {
                'success': True,
                'game_status': {
                    'total_cells': summary.get('total_cells', 0),
                    'known_cells': summary.get('known_cells', 0),
                    'symbol_distribution': summary.get('symbol_distribution', {}),
                    'bounds': summary.get('bounds', [])
                }
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def convert_actions_to_game_actions(self, solve_result: Dict[str, Any]) -> List[GameAction]:
        """
        Convertit les actions du solveur en objets GameAction exécutables.

        Args:
            solve_result: Résultat du solveur contenant les actions

        Returns:
            Liste d'objets GameAction
        """
        game_actions = []
        
        # Récupérer les actions depuis solve_result['actions']
        actions_dict = solve_result.get('actions', {})
        print(f"[DEBUG] convert_actions_to_game_actions: actions_dict = {actions_dict}")

        # Récupérer les limites de la zone analysée depuis le résultat
        analysis_result = solve_result.get('analysis_result', {})
        grid_bounds = analysis_result.get('grid_bounds', (-38, -28, 50, 16))  # valeurs par défaut
        print(f"[DEBUG] Limites de la zone analysée: {grid_bounds}")
        
        start_x, start_y, end_x, end_y = grid_bounds
        
        # Calculer la taille de la zone
        zone_width = end_x - start_x
        zone_height = end_y - start_y
        print(f"[DEBUG] Taille de la zone: {zone_width}x{zone_height}")

        # Actions sûres (clics gauches)
        safe_actions = actions_dict.get('safe', [])
        print(f"[DEBUG] Actions sûres brutes: {safe_actions}")
        
        for x, y in safe_actions:
            # Garder les coordonnées absolues de la grille
            print(f"[DEBUG] Utilisation coordonnées absolues: ({x}, {y})")
            
            action = GameAction(
                action_type=ActionType.CLICK_LEFT,
                grid_x=x,
                grid_y=y,
                confidence=1.0,  # Les actions sûres ont confiance maximale
                description=f"Clic sûr sur ({x}, {y})"
            )
            game_actions.append(action)

        # Actions drapeau (clics droits)
        flag_actions = actions_dict.get('flag', [])
        print(f"[DEBUG] Actions drapeau brutes: {flag_actions}")
        
        for x, y in flag_actions:
            # Garder les coordonnées absolues de la grille
            print(f"[DEBUG] Utilisation coordonnées absolues: ({x}, {y})")
            
            action = GameAction(
                action_type=ActionType.CLICK_RIGHT,
                grid_x=x,
                grid_y=y,
                confidence=1.0,  # Les actions de drapeau ont confiance maximale
                description=f"Drapeau sur ({x}, {y})"
            )
            game_actions.append(action)

        print(f"[DEBUG] GameActions créées: {len(game_actions)}")
        return game_actions

    def solve_from_db_path(self, db_path: Optional[str] = None,
                          screenshot_path: Optional[str] = None,
                          game_id: str = None, iteration_num: int = None) -> Dict[str, Any]:
        """
        Résoudre une grille à partir d'une base de données existante

        Args:
            db_path: Chemin vers la GridDB (optionnel, utilise la valeur par défaut)
            screenshot_path: Chemin vers le screenshot original pour l'overlay

        Returns:
            Dict avec les résultats de la résolution
        """
        start_time = time.time()

        db_path = db_path or self.db_path

        if not os.path.exists(db_path):
            return {
                'success': False,
                'message': f"Base de données introuvable: {db_path}",
                'performance': {'total_time': time.time() - start_time}
            }

        try:
            print(f"[SOLVE] Résolution à partir de: {db_path}")

            # 1. Charger la DB
            grid_db = GridDB(db_path)

            # 2. Initialiser l'analyzer et le solveur
            analyzer = GridAnalyzer(grid_db)
            solver = HybridSolver(analyzer)

            # Générer l'overlay de segmentation (intermédiaire)
            segmentation_overlay_path = None
            if self.generate_overlays and screenshot_path and self.segmentation_visualizer:
                try:
                    print("[OVERLAY] Génération de l'overlay de segmentation...")
                    segmentation_overlay_path = self.segmentation_visualizer.visualize(
                        analyzer, solver.segmentation, screenshot_path, game_id, iteration_num
                    )
                except Exception as e:
                    print(f"[WARN] Erreur overlay segmentation: {e}")

            # 3. Résoudre
            print("[SOLVE] Lancement du solveur hybride CSP...")
            solve_start = time.time()
            solver.solve()
            solve_duration = time.time() - solve_start

            # 4. Sauvegarder les résultats dans la DB
            solver.save_to_db(grid_db)
            grid_db.flush_to_disk()

            # 5. Collecter les statistiques
            safe_cells = solver.get_safe_cells()
            flag_cells = solver.get_flag_cells()
            total_cells = len(safe_cells) + len(flag_cells)

            # 6. Générer l'overlay si demandé
            overlay_path = None
            if self.generate_overlays and screenshot_path:
                print("[OVERLAY] Génération de l'overlay final...")
                overlay_path = self.overlay_generator.generate_overlay_from_db(
                    screenshot_path, grid_db, game_id, iteration_num
                )

            # 7. Résumé des probabilités pour debug
            prob_summary = {}
            for zone_id, prob in solver.zone_probabilities.items():
                zone = next((z for z in solver.segmentation.zones if z.id == zone_id), None)
                if zone:
                    prob_summary[zone_id] = {
                        'probability': prob,
                        'size': len(zone.cells)
                    }

            return {
                'success': True,
                'message': 'Résolution terminée avec succès',
                'statistics': {
                    'safe_cells': len(safe_cells),
                    'flag_cells': len(flag_cells),
                    'total_actions': total_cells,
                    'zones_analyzed': len(solver.segmentation.zones),
                    'components_solved': len(solver.segmentation.components),
                    'probability_summary': prob_summary
                },
                'actions': {
                    'safe': [(x, y) for x, y in safe_cells],
                    'flag': [(x, y) for x, y in flag_cells]
                },
                'performance': {
                    'total_time': time.time() - start_time,
                    'solve_time': solve_duration,
                    'cells_per_second': total_cells / solve_duration if solve_duration > 0 else 0
                },
                'overlay_path': overlay_path,
                'segmentation_overlay_path': segmentation_overlay_path
            }

        except Exception as e:
            import traceback
            error_msg = f"Erreur lors de la résolution: {str(e)}"
            print(f"[ERREUR] {error_msg}")
            traceback.print_exc()

            return {
                'success': False,
                'message': error_msg,
                'performance': {'total_time': time.time() - start_time}
            }
