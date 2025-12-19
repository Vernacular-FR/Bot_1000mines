from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import re

from src.lib.s3_storage.controller import StorageController
from src.lib.s4_solver.controller import SolverController
from src.lib.s2_vision.facade import VisionAPI, VisionControllerConfig
from src.lib.s2_vision.s23_vision_to_storage import matches_to_upsert
from src.config import CELL_BORDER, CELL_SIZE


class GameSolverServiceV2:
    """
    Service de résolution basé sur Storage + OptimizedSolver (CSP-only).
    Pas de dépendances GridDB/tensor/navigation.
    """

    def __init__(self, storage: StorageController | None = None):
        self.storage = storage or StorageController()
        self.solver = SolverController(storage=self.storage)
        self._bounds_pattern = re.compile(r"zone_(?P<sx>-?\d+)_(?P<sy>-?\d+)_(?P<ex>-?\d+)_(?P<ey>-?\d+)")

    def solve_snapshot(self) -> Dict[str, Any]:
        """
        Exécute le solver CSP sur l'état actuel de storage et retourne actions + stats.
        Overlays sont gérés côté solver via le contexte global.
        """
        update = self.solver.solve_with_update()
        if not update:
            return {'success': False, 'actions': [], 'stats': None}
        return {
            'success': True,
            'actions': update.actions,
            'stats': update.stats,
            'storage_upsert': update.storage_upsert,
        }

    def solve_from_file_with_vision(
        self,
        screenshot_path: str | Path,
        *,
        export_root: str | Path | None = None,
        emit_solver_overlays: bool = True,
    ) -> Dict[str, Any]:
        """
        Pipeline complet : vision (template matcher) -> storage.upsert -> solver.
        """
        screenshot = Path(screenshot_path)
        bounds = self._parse_bounds(screenshot)
        if not bounds:
            return {'success': False, 'message': "bounds introuvables", 'actions': [], 'stats': None}

        start_x, start_y, end_x, end_y = bounds
        grid_width = end_x - start_x + 1
        grid_height = end_y - start_y + 1
        stride = CELL_SIZE + CELL_BORDER

        export_root = Path(export_root) if export_root else None

        vision = VisionAPI(VisionControllerConfig(overlay_output_dir=export_root))
        known_set = set(self.storage.get_known()) if self.storage else set()
        matches = vision.analyze_screenshot(
            screenshot_path=str(screenshot),
            grid_top_left=(0, 0),
            grid_size=(grid_width, grid_height),
            stride=stride,
            overlay=bool(export_root),
            known_set=known_set,
            bounds_offset=(start_x, start_y),
        )

        analysis_result = {
            "bounds": bounds,
            "matches": matches,
            "stride": stride,
            "cell_size": CELL_SIZE,
            "export_root": export_root,
        }

        return self.solve_from_analysis_to_solver(
            str(screenshot),
            analysis_result=analysis_result,
            emit_solver_overlays=emit_solver_overlays,
        )


    def solve_from_analysis_to_solver(
        self,
        screenshot_path: str,
        analysis_result: Optional[Dict[str, Any]] = None,
        *,
        emit_solver_overlays: bool = True,
    ) -> Dict[str, Any]:
        """
        Pipeline complet : applique un upsert pré-calculé (vision) puis résout.
        """
        if analysis_result is None:
            return {'success': False, 'message': "analysis_result requis", 'actions': [], 'stats': None}

        bounds = analysis_result.get("bounds")
        matches = analysis_result.get("matches")
        stride = analysis_result.get("stride")
        cell_size = analysis_result.get("cell_size", CELL_SIZE)
        if not (bounds and matches is not None and stride):
            return {'success': False, 'message': "bounds/matches manquants", 'actions': [], 'stats': None}

        upsert = matches_to_upsert(bounds, matches)
        self.storage.upsert(upsert)

        result = self.solve_snapshot()
        result.update({
            "bounds": bounds,
            "stride": stride,
            "cells": self.storage.get_cells(bounds),
        })
        return result



    def _parse_bounds(self, screenshot: Path) -> Optional[Tuple[int, int, int, int]]:
        match = self._bounds_pattern.search(screenshot.stem)
        if not match:
            return None
        return (
            int(match.group("sx")),
            int(match.group("sy")),
            int(match.group("ex")),
            int(match.group("ey")),
        )

        upsert = analysis_result.get("storage_upsert")
        actions = analysis_result.get("actions")
        stats = analysis_result.get("stats")
        if upsert:
            self.storage.upsert(upsert)
        return {'success': True, 'actions': actions or [], 'stats': stats}

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
