"""
Service d'analyse optimisé avec template matching fixe
Version simplifiée sans fichiers temporaires
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List, Iterable

import numpy as np

from PIL import Image, ImageDraw

from src.lib.s3_tensor.grid_state import GamePersistence, GridDB
from src.lib.s2_recognition.template_matching_fixed import (
    FixedTemplateMatcher,
    build_grid_analysis_from_results,
)
from src.lib.s3_tensor.mapper import VisionToGameMapper
from src.lib.s3_tensor.runtime import ensure_tensor_runtime
from src.lib.s3_tensor.tensor_grid import TensorGrid
from src.lib.s3_tensor.types import CellType
from src.lib.config import PATHS, CELL_SIZE, CELL_BORDER
from src.lib.s2_recognition.s22_Neural_engine.cnn.src.api import CNNCellClassifier

CNN_NUMBER_ACCEPT_THRESHOLD = 0.50


class OptimizedAnalysisService:
    """Service d'analyse optimisé avec template matching fixe"""

    def __init__(
        self,
        generate_overlays=True,
        paths: Dict[str, str] = None,
        enable_cnn: bool = True,
    ):
        """
        Initialise le service optimisé avec template matching
        
        Args:
            generate_overlays: Générer les overlays (peut être désactivé pour vitesse)
            paths: Chemins personnalisés pour les fichiers (obligatoire)
        """
        # Utiliser systématiquement le template matching fixe
        self.template_matcher = FixedTemplateMatcher("src/lib/s2_recognition/s21_templates/symbols")
        self.generate_overlays = generate_overlays
        self.paths = paths or PATHS
        
        # GridDB avec chemin obligatoire
        grid_db_path = self.paths.get('grid_db')
        if not grid_db_path:
            raise ValueError("grid_db est obligatoire dans paths pour OptimizedAnalysisService")
        self.grid_db = GridDB(db_path=grid_db_path)
        self.tensor_runtime = ensure_tensor_runtime(self.paths)
        
        # Configuration des chemins
        self.base_path = os.getcwd()
        self.screenshots_path = os.path.abspath(self.paths.get('zone', self.paths.get('zone_screenshots', 'temp/zones')))
        self.output_path = os.path.abspath(self.paths.get('analysis', self.paths.get('analysis_reports', 'temp/analysis')))
        self.analysis_overlays_path = os.path.abspath(self.paths.get('analysis', self.paths.get('analysis_overlays', 'temp/analysis')))
        
        print("[INFO] Service optimisé initialisé avec template matching fixe (par défaut)")
        
        # Créer les dossiers de sortie
        os.makedirs(self.output_path, exist_ok=True)
        os.makedirs(self.analysis_overlays_path, exist_ok=True)
        
        # Initialiser le générateur d'overlays si nécessaire
        if self.generate_overlays:
            from src.lib.s4_solver.overlays.solver_overlay_generator import SolverOverlayGenerator
            solver_dir = self.paths.get('solver')
            if not solver_dir:
                raise ValueError("solver est obligatoire dans paths pour OptimizedAnalysisService")
            self.overlay_generator = SolverOverlayGenerator(output_dir=solver_dir)
        else:
            self.overlay_generator = None

        self.cnn_classifier: Optional[CNNCellClassifier] = None
        self.enable_cnn = enable_cnn
        if self.enable_cnn:
            self._init_cnn_classifier()

    def _init_cnn_classifier(self) -> None:
        try:
            cnn_root = Path("src/lib/s2_recognition/s22_Neural_engine/cnn")
            config_path = cnn_root / "config.yaml"
            model_path = cnn_root / "artifacts/best_model.pth"
            if not config_path.exists() or not model_path.exists():
                print(
                    "[CNN] Config ou modèle introuvable, désactivation du CNN "
                    f"({config_path} / {model_path})"
                )
                return
            self.cnn_classifier = CNNCellClassifier(
                config_path=config_path, model_path=model_path
            )
            print("[CNN] Classifier chargé, CNN actif en production.")
        except Exception as exc:
            print(f"[CNN] Impossible de charger le classifier: {exc}")
            self.cnn_classifier = None

    def _predict_with_cnn(
        self, patches: List[np.ndarray]
    ) -> List[Tuple[str, float]]:
        if not patches or not self.cnn_classifier:
            return []
        predictions = self.cnn_classifier.predict_patches(patches)
        return [
            (pred["label"], float(pred["confidence"]))
            for pred in predictions
        ]

    def analyze_from_path(self, image_path: str, zone_bounds: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Analyse un screenshot spécifique depuis un chemin de fichier.
        Version simplifiée sans fichier temporaire.

        Args:
            image_path: Chemin vers l'image à analyser
            zone_bounds: Coordonnées de la zone (start_x, start_y, end_x, end_y) pour coordonnées absolues

        Returns:
            Dict avec le résultat de l'analyse
        """
        try:
            if not os.path.exists(image_path):
                return {
                    'success': False,
                    'message': f"Fichier image introuvable: {image_path}",
                    'db_path': None,
                    'game_status': {},
                    'summary': {}
                }

            # Vérifier que le chemin de la base de données est configuré
            grid_db_path = self.paths.get('grid_db')
            if not grid_db_path:
                return {
                    'success': False,
                    'error': 'grid_db non trouvé dans les chemins',
                    'message': 'Chemin de base de données non configuré',
                    'db_path': None,
                    'game_status': {},
                    'summary': {}
                }
            
            # Créer le dossier si nécessaire
            db_dir = os.path.dirname(grid_db_path)
            os.makedirs(db_dir, exist_ok=True)
            
            # Analyser directement l'image originale
            result = self.analyze_single_screenshot_optimized(
                image_path, generate_overlays=self.generate_overlays, zone_bounds=zone_bounds
            )
            
            # Si succès, la base de données est déjà sauvegardée dans grid_db_path
            if result['success']:
                result['db_path'] = grid_db_path

            return result

        except Exception as e:
            print(f"[ERREUR] Erreur dans analyze_from_path: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f"Erreur lors de l'analyse: {str(e)}",
                'db_path': None,
                'game_status': {},
                'summary': {}
            }

    def build_cell_state_index(
        self, zone_bounds: Tuple[int, int, int, int], with_metrics: bool = False
    ) -> Any:
        """
        API publique pour exposer l'index des cellules (utilisé par la roadmap Semaine 1).
        """
        state_index = self._build_cell_state_index(zone_bounds)
        if with_metrics:
            return state_index, self._compute_state_metrics(state_index, zone_bounds)
        return state_index

    def analyze_single_screenshot_optimized(self, screenshot_path: str, 
                                          generate_overlays: bool = None,
                                          zone_bounds: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Analyse optimisée d'un seul fichier screenshot avec template matching fixe.
        """
        start_time = time.time()
        
        print(f"[ANALYSE] Analyse optimisée: {os.path.basename(screenshot_path)}")
        
        try:
            # Vérifier que le fichier existe
            if not os.path.exists(screenshot_path):
                return {
                    'success': False,
                    'message': f"Fichier introuvable: {screenshot_path}",
                    'cell_count': 0,
                    'performance': {'total_time': time.time() - start_time}
                }
            
            # Utiliser les coordonnées absolues fournies ou parser depuis le nom du fichier
            filename = os.path.basename(screenshot_path)
            if zone_bounds:
                start_x, start_y, end_x, end_y = zone_bounds
                print(f"[DEBUG] Utilisation coordonnées absolues fournies: {zone_bounds}")
            else:
                # Parser le nom du fichier (sans extension)
                name_without_ext = os.path.splitext(filename)[0]  # Enlever .png
                parts = name_without_ext.replace('zone_', '').split('_')
                if len(parts) < 4:
                    return {
                        'success': False,
                        'message': 'Format de fichier non reconnu (manque coordonnées)',
                        'cell_count': 0,
                        'performance': {'total_time': time.time() - start_time}
                    }
                
                start_x, start_y, end_x, end_y = map(int, parts[:4])
                print(f"[DEBUG] Coordonnées parsées depuis le nom: {(start_x, start_y, end_x, end_y)}")
            
            # Charger l'image
            image = Image.open(screenshot_path)
            
            # Construire un index d'état pré-existant (GridDB)
            zone_tuple = (start_x, start_y, end_x, end_y)
            build_index_result = self.build_cell_state_index(zone_tuple, with_metrics=True)
            if isinstance(build_index_result, tuple):
                state_index, state_metrics = build_index_result
            else:
                state_index = build_index_result
                state_metrics = self._compute_state_metrics(state_index, zone_tuple)
            print(
                "[STATE] total=%d known=%d skipped=%d"
                % (
                    state_metrics["cells_total"],
                    state_metrics["cells_known"],
                    state_metrics["cells_skipped"],
                )
            )
            filtering_info = self._classify_cells_for_filtering(
                state_index, zone_tuple
            )
            print(
                "[FILTER] candidates=%d unknown=%d known=%d"
                % (
                    len(filtering_info["candidate_cells"]),
                    len(filtering_info["truly_unknown_cells"]),
                    len(filtering_info["known_cells"]),
                )
            )
            overlay_paths = []
            if self.generate_overlays:
                filter_overlay = self._generate_filter_overlay(
                    screenshot_path, zone_tuple, filtering_info, order=1
                )
                if filter_overlay:
                    overlay_paths.append(filter_overlay)
            
            image_gray = image.convert("L")
            image_np = np.array(image_gray, dtype=np.float32)
            grid_results = {}
            pass_overlays = []
            previous_pass_results: Dict[str, Dict[Tuple[int, int], Tuple[str, float]]] = {}
            passes = self._build_analysis_passes(filtering_info, state_index)
            pass_metrics: List[Dict[str, Any]] = []

            for idx, analysis_pass in enumerate(passes):
                pass_input = len(analysis_pass["cells"])
                pass_start = time.time()
                pass_results = self._run_analysis_pass(
                    analysis_pass, image_np, zone_tuple
                )
                pass_duration = time.time() - pass_start
                pass_metrics.append(
                    {
                        "name": analysis_pass["name"],
                        "order": analysis_pass["order"],
                        "input_cells": pass_input,
                        "matched_cells": len(pass_results),
                        "duration": pass_duration,
                    }
                )
                print(
                    "[PASS] %s input=%d matched=%d time=%.3fs"
                    % (
                        analysis_pass["name"],
                        pass_input,
                        len(pass_results),
                        pass_duration,
                    )
                )
                grid_results.update(pass_results)
                # Flush DB après unrevealed_check pour garantir que known=True soit visible
                if pass_results:
                    if analysis_pass["name"] == "unrevealed_check":
                        self.grid_db.flush_to_disk()
                        confirmed_unrevealed = {
                            coord for coord, (symbol, _) in pass_results.items() if symbol == "unrevealed"
                        }
                        if confirmed_unrevealed:
                            for later_pass in passes[idx + 1 :]:
                                later_pass["cells"] = [
                                    cell for cell in later_pass["cells"] if cell not in confirmed_unrevealed
                                ]
                    elif analysis_pass["name"] == "empty_refresh":
                        confirmed_empty = {
                            coord for coord, (symbol, _) in pass_results.items() if symbol == "empty"
                        }
                        if confirmed_empty:
                            for later_pass in passes[idx + 1 :]:
                                later_pass["cells"] = [
                                    cell for cell in later_pass["cells"] if cell not in confirmed_empty
                                ]
                    elif analysis_pass["name"] == "exploded_check":
                        confirmed_mines = {
                            coord for coord, (symbol, _) in pass_results.items() if symbol == "exploded"
                        }
                        if confirmed_mines:
                            for later_pass in passes[idx + 1 :]:
                                later_pass["cells"] = [
                                    cell for cell in later_pass["cells"] if cell not in confirmed_mines
                                ]
                if self.generate_overlays and pass_results:
                    pass_overlay = self._generate_pass_overlay(
                        screenshot_path,
                        zone_tuple,
                        analysis_pass["name"],
                        analysis_pass["order"],
                        pass_results,
                    )
                    if pass_overlay:
                        pass_overlays.append(pass_overlay)

                previous_pass_results[analysis_pass["name"]] = pass_results

            overlay_paths.extend(pass_overlays)
            grid_results = self._fill_missing_results(
                grid_results, state_index, zone_tuple
            )

            # Construire GridAnalysis à partir des résultats
            try:
                grid_analysis = build_grid_analysis_from_results(screenshot_path, grid_results, zone_bounds)
            except Exception as e:
                print(f"[ERREUR] Erreur dans build_grid_analysis_from_results: {e}")
                raise
            
            print(f"[INFO] Template matching: {len(grid_results)} cellules reconnues")
            
            if not grid_analysis or not grid_analysis.cells:
                return {
                    'success': False,
                    'message': 'Aucune cellule détectée',
                    'cell_count': 0,
                    'performance': {'total_time': time.time() - start_time}
                }
            
            # Mettre à jour la DB GridDB sans supprimer l'existant
            for (x, y), analysis in grid_analysis.cells.items():
                game_symbol = VisionToGameMapper.map_cell_type(analysis.cell_type)
                # Convertir CellSymbol en string pour GridDB
                cell_type = game_symbol.value
                self.grid_db.add_cell(x, y, {
                    "type": cell_type,
                    "confidence": analysis.confidence,
                    "state": "TO_PROCESS",
                    "known": cell_type not in {"unknown", "unrevealed"},
                })

            # Sauvegarde TensorGrid miroir
            self._write_tensor_grid(grid_analysis, zone_tuple)
            
            # Sauvegarder la DB
            self.grid_db.flush_to_disk()
            
            # Générer les overlays si demandé
            should_generate = generate_overlays if generate_overlays is not None else self.generate_overlays
            
            # Désactivé - l'overlay final est géré par GameSolverService. Les overlays d’analyse sont ajoutés ci-dessus.
            
            # Calculer les statistiques de performance
            total_time = time.time() - start_time
            
            diff_path = self._save_analysis_diff(
                filtering_info,
                state_index,
                grid_results,
                zone_tuple,
                os.path.basename(screenshot_path),
            )
            tm_stats = self.template_matcher.get_runtime_stats()
            if tm_stats.get("shadow_divergent"):
                print(
                    "[SHADOW] Divergences détectées "
                    f"({tm_stats['shadow_divergent']}/{tm_stats['shadow_total']} "
                    f"= {tm_stats['shadow_ratio']:.2%})"
                )
            cells_scanned = len(grid_analysis.cells)
            scan_ratio = (
                cells_scanned / state_metrics["cells_total"]
                if state_metrics["cells_total"] > 0
                else 0.0
            )
            result = {
                'success': True,
                'filename': filename,
                'path': screenshot_path,
                'grid_bounds': zone_tuple,  # Coordonnées absolues
                'cell_count': cells_scanned,
                'overlay_paths': overlay_paths,
                'overlay_path': overlay_paths[0] if overlay_paths else None,
                'performance': {
                    'total_time': total_time,
                    'cells_per_second': len(grid_analysis.cells) / total_time if total_time > 0 else 0,
                    'cache_stats': {'template_matching': True}
                },
                'metrics': {
                    "cells_total": state_metrics["cells_total"],
                    "cells_scanned": cells_scanned,
                    "cells_candidates": len(filtering_info["candidate_cells"]),
                    "cells_skipped": state_metrics["cells_skipped"],
                    "scan_ratio": scan_ratio,
                    "tm_backend": tm_stats.get("backend"),
                    "tm_total_calls": tm_stats.get("total_calls"),
                    "tm_opencv_primary": tm_stats.get("opencv_primary"),
                    "tm_hybrid_primary": tm_stats.get("hybrid_primary"),
                    "tm_fallback_used": tm_stats.get("fallback_used"),
                    "tm_shadow_divergent": tm_stats.get("shadow_divergent"),
                    "tm_shadow_total": tm_stats.get("shadow_total"),
                },
                'filtering': filtering_info,
                'diff_path': diff_path,
                'analysis_passes': [p["name"] for p in passes if p["cells"]],
                'pass_metrics': pass_metrics,
                'state_metrics': state_metrics,
            }
            
            print(f"[SUCCES] {filename}: {len(grid_analysis.cells)} cellules en {total_time:.2f}s")
            
            return result

        except Exception as e:
            print(f"[ERREUR] Exception lors de l'analyse: {e}")
            filename = os.path.basename(screenshot_path)
            return {
                'filename': filename,
                'path': screenshot_path,
                'success': False,
                'error': str(e),
                'cell_count': 0,
                'performance': {'total_time': time.time() - start_time}
            }

    def _write_tensor_grid(self, grid_analysis, bounds: Tuple[int, int, int, int]) -> None:
        start_x, start_y, end_x, end_y = bounds
        width = end_x - start_x + 1
        height = end_y - start_y + 1

        codes = np.full((height, width), TensorGrid.encode_cell_type(CellType.UNKNOWN), dtype=np.int8)
        confidences = np.zeros((height, width), dtype=np.float32)
        dirty_mask = np.ones((height, width), dtype=bool)

        for (x, y), analysis in grid_analysis.cells.items():
            rel_x = x - start_x
            rel_y = y - start_y
            if 0 <= rel_x < width and 0 <= rel_y < height:
                codes[rel_y, rel_x] = TensorGrid.encode_cell_type(analysis.cell_type)
                confidences[rel_y, rel_x] = float(max(0.0, min(1.0, analysis.confidence)))

        tick_id = self.tensor_runtime.next_tick()
        self.tensor_runtime.tensor_grid.update_region(
            bounds,
            codes,
            confidences,
            dirty_mask=dirty_mask,
            tick_id=tick_id,
        )
        self.tensor_runtime.hint_cache.publish_dirty_set(bounds=bounds, priority=5, tick_id=tick_id)
        snapshot = self.tensor_runtime.tensor_grid.snapshot()
        self.tensor_runtime.trace_recorder.capture(
            tick_id,
            snapshot,
            {"stage": "S2_analyze", "cells": grid_analysis.get_cell_count()},
        )

    def _build_cell_state_index(self, bounds: Tuple[int, int, int, int]) -> Dict[Tuple[int, int], Dict[str, Any]]:
        start_x, start_y, end_x, end_y = bounds
        index: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for cell in self.grid_db.get_all_cells():
            x, y = cell["x"], cell["y"]
            if start_x <= x <= end_x and start_y <= y <= end_y:
                index[(x, y)] = {
                    "type": cell.get("type", "unknown"),
                    "confidence": cell.get("confidence", 0.0),
                    "state": cell.get("state", ""),
                    "known": cell.get("known", cell["type"] not in {"unknown", "unrevealed"}),
                }
        return index

    def _compute_state_metrics(self, state_index: Dict[Tuple[int, int], Dict[str, Any]], bounds: Tuple[int, int, int, int]) -> Dict[str, Any]:
        start_x, start_y, end_x, end_y = bounds
        total_cells = (end_x - start_x + 1) * (end_y - start_y + 1)
        stable_types = {"empty", "flag", "mine", "decor"} | {f"number_{i}" for i in range(1, 9)}
        cells_skipped = 0
        cells_known = 0
        for _, cell in state_index.items():
            if cell["type"] in stable_types:
                cells_skipped += 1
            if cell["type"] != "unknown":
                cells_known += 1
        return {
            "cells_total": total_cells,
            "cells_known": cells_known,
            "cells_skipped": cells_skipped,
        }

    def _generate_preanalysis_overlay(self, screenshot_path: str, bounds: Tuple[int, int, int, int], state_index: Dict[Tuple[int, int], Dict[str, Any]], order: int = 0) -> Optional[str]:
        try:
            base_image = Image.open(screenshot_path).convert("RGBA")
            overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            start_x, start_y, end_x, end_y = bounds
            cell_size = CELL_SIZE
            cell_total = CELL_SIZE + CELL_BORDER

            stable_types = {"empty", "flag", "mine"} | {f"number_{i}" for i in range(1, 9)}
            unknown_types = {"unknown", "unrevealed"}
            color_map = {
                "empty": (0, 200, 120, 160),
                "flag": (255, 80, 80, 170),
                "mine": (160, 0, 120, 160),
                "unknown": (255, 140, 0, 150),
                "unrevealed": (255, 140, 0, 150),
            }
            for i in range(1, 9):
                color_map[f"number_{i}"] = (
                    40,
                    120 + i * 10,
                    255 - i * 15,
                    150,
                )
            default_new_color = (0, 90, 200, 90)
            default_known_color = (0, 180, 0, 120)
            for gx in range(start_x, end_x + 1):
                for gy in range(start_y, end_y + 1):
                    cell = state_index.get((gx, gy))
                    if cell is None:
                        fill = default_new_color  # nouvelle cellule hors DB
                    else:
                        cell_type = cell.get("type", "unknown")
                        if cell_type in unknown_types:
                            fill = color_map["unknown"]
                        elif cell_type in stable_types:
                            fill = color_map.get(cell_type, default_known_color)
                        else:
                            fill = default_known_color

                    offset_x = (gx - start_x) * cell_total
                    offset_y = (gy - start_y) * cell_total
                    draw.rectangle(
                        [
                            (offset_x, offset_y),
                            (offset_x + cell_size, offset_y + cell_size),
                        ],
                        fill=fill,
                    )

            combined = Image.alpha_composite(base_image, overlay)
            filename = self._build_overlay_filename(screenshot_path, f"stage{order:02d}_preanalysis")
            overlay_path = os.path.join(self.analysis_overlays_path, filename)
            os.makedirs(self.analysis_overlays_path, exist_ok=True)
            combined.convert("RGB").save(overlay_path, optimize=True)
            print(f"[OVERLAY] Pré-analyse sauvegardée: {overlay_path}")
            return overlay_path
        except Exception as e:
            print(f"[WARN] Impossible de générer l'overlay pré-analyse: {e}")
            return None

    def _build_overlay_filename(self, screenshot_path: str, suffix: str) -> str:
        base = os.path.splitext(os.path.basename(screenshot_path))[0]
        return f"{base}_{suffix}.png"

    def _classify_cells_for_filtering(
        self,
        state_index: Dict[Tuple[int, int], Dict[str, Any]],
        bounds: Tuple[int, int, int, int],
    ) -> Dict[str, Any]:
        start_x, start_y, end_x, end_y = bounds
        stable_types = {"empty", "flag", "mine"} | {f"number_{i}" for i in range(1, 9)}
        unrevealed_type = {"unrevealed"}

        known_cells = []
        truly_unknown_cells = []

        for gx in range(start_x, end_x + 1):
            for gy in range(start_y, end_y + 1):
                cell = state_index.get((gx, gy))
                if cell is None:
                    truly_unknown_cells.append((gx, gy))
                    continue
                is_known = cell.get("known", cell["type"] not in {"unknown", "unrevealed"})
                if is_known:
                    known_cells.append((gx, gy))
                else:
                    truly_unknown_cells.append((gx, gy))

        return {
            "known_cells": known_cells,
            "truly_unknown_cells": truly_unknown_cells,
            "candidate_cells": truly_unknown_cells,
        }

    def _generate_filter_overlay(
        self,
        screenshot_path: str,
        bounds: Tuple[int, int, int, int],
        filtering_info: Dict[str, Any],
        order: int = 1,
    ) -> Optional[str]:
        try:
            base_image = Image.open(screenshot_path).convert("RGBA")
            overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            start_x, start_y, end_x, end_y = bounds
            cell_total = CELL_SIZE + CELL_BORDER

            candidate_set = set(filtering_info["candidate_cells"])
            known_set = set(filtering_info["known_cells"])

            for gx in range(start_x, end_x + 1):
                for gy in range(start_y, end_y + 1):
                    offset_x = (gx - start_x) * cell_total
                    offset_y = (gy - start_y) * cell_total
                    if (gx, gy) in candidate_set:
                        fill = (255, 80, 0, 140)  # orange : vraiment inconnues à analyser
                    elif (gx, gy) in known_set:
                        fill = (70, 180, 70, 110)  # vert : déjà connues, ignorées
                    else:
                        fill = (0, 90, 200, 90)   # bleu : jamais vues (incluses dans candidate_cells)
                    draw.rectangle(
                        [
                            (offset_x, offset_y),
                            (offset_x + CELL_SIZE, offset_y + CELL_SIZE),
                        ],
                        fill=fill,
                    )

            combined = Image.alpha_composite(base_image, overlay)
            filename = self._build_overlay_filename(
                screenshot_path,
                "filtering",
            )
            overlay_path = os.path.join(self.analysis_overlays_path, filename)
            os.makedirs(self.analysis_overlays_path, exist_ok=True)
            combined.convert("RGB").save(overlay_path, optimize=True)
            print(f"[OVERLAY] Filtrage sauvegardé: {overlay_path}")
            return overlay_path
        except Exception as e:
            print(f"[WARN] Impossible de générer l'overlay de filtrage: {e}")
            return None

    def _build_analysis_passes(
        self,
        filtering_info: Dict[str, Any],
        state_index: Dict[Tuple[int, int], Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        candidate_cells = filtering_info.get("candidate_cells", [])

        passes = []
        unknown_cells = filtering_info.get("truly_unknown_cells", [])
        if unknown_cells:
            passes.append(
                {
                    "order": 1,
                    "name": "unrevealed_check",
                    "cells": list(unknown_cells),
                }
            )

        if candidate_cells:
            passes.append({"order": 2, "name": "empty_refresh", "cells": list(candidate_cells)})
            passes.append({"order": 3, "name": "exploded_check", "cells": list(candidate_cells)})
            if self.cnn_classifier:
                passes.append({"order": 4, "name": "cnn_refresh", "cells": list(candidate_cells)})
            else:
                passes.append({"order": 4, "name": "numbers_refresh", "cells": list(candidate_cells)})
        return passes

    def _run_analysis_pass(
        self,
        analysis_pass: Dict[str, Any],
        image_np: np.ndarray,
        bounds: Tuple[int, int, int, int],
    ) -> Dict[Tuple[int, int], Tuple[str, float]]:
        results = {}
        start_x, start_y, end_x, end_y = bounds
        cell_total = CELL_SIZE + CELL_BORDER

        if analysis_pass["name"] == "cnn_refresh":
            return self._run_cnn_analysis_pass(analysis_pass, image_np, bounds)
        if analysis_pass["name"] == "exploded_check" and self.cnn_classifier:
            return self._run_cnn_analysis_pass(
                analysis_pass, image_np, bounds, allowed_labels={"exploded"}
            )

        for gx, gy in analysis_pass["cells"]:
            rel_x = (gx - start_x) * cell_total + CELL_SIZE // 2
            rel_y = (gy - start_y) * cell_total + CELL_SIZE // 2
            if 0 <= rel_x < image_np.shape[1] and 0 <= rel_y < image_np.shape[0]:
                match_result = self.template_matcher.match_template_at(
                    image_np, rel_x, rel_y, analysis_pass["name"]
                )
                if match_result:
                    symbol, confidence = match_result
                    results[(gx, gy)] = (symbol, confidence)
                    if analysis_pass["name"] == "unrevealed_check" and symbol == "unrevealed":
                        self.grid_db.add_cell(gx, gy, {
                            "type": "unrevealed",
                            "confidence": confidence,
                            "state": "TO_PROCESS",
                            "known": False,
                        })
        return results

    def _run_cnn_analysis_pass(
        self,
        analysis_pass: Dict[str, Any],
        image_np: np.ndarray,
        bounds: Tuple[int, int, int, int],
        allowed_labels: Optional[Set[str]] = None,
    ) -> Dict[Tuple[int, int], Tuple[str, float]]:
        if not self.cnn_classifier:
            return {}

        results: Dict[Tuple[int, int], Tuple[str, float]] = {}
        start_x, start_y, _, _ = bounds
        cell_total = CELL_SIZE + CELL_BORDER

        coords: List[Tuple[int, int]] = []
        patches: List[np.ndarray] = []
        for gx, gy in analysis_pass["cells"]:
            rel_x = (gx - start_x) * cell_total
            rel_y = (gy - start_y) * cell_total
            patch = image_np[
                rel_y : rel_y + CELL_SIZE,
                rel_x : rel_x + CELL_SIZE,
            ]
            if patch.shape != (CELL_SIZE, CELL_SIZE):
                continue
            coords.append((gx, gy))
            patches.append(patch.astype(np.uint8))

        predictions = self._predict_with_cnn(patches)
        if not predictions:
            return results

        default_threshold = getattr(self.cnn_classifier, "accept_threshold", 0.8)
        for (gx, gy), (label, confidence) in zip(coords, predictions):
            if allowed_labels and label not in allowed_labels:
                continue
            threshold = default_threshold
            if label.startswith("number_"):
                threshold = min(default_threshold, CNN_NUMBER_ACCEPT_THRESHOLD)
            if confidence < threshold:
                continue
            symbol = "exploded" if label == "exploded" else label
            results[(gx, gy)] = (symbol, confidence)
        return results

    def _generate_pass_overlay(
        self,
        screenshot_path: str,
        bounds: Tuple[int, int, int, int],
        pass_name: str,
        pass_order: int,
        pass_results: Dict[Tuple[int, int], Tuple[str, float]],
    ) -> Optional[str]:
        try:
            base_image = Image.open(screenshot_path).convert("RGBA")
            overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            start_x, start_y, end_x, end_y = bounds
            cell_total = CELL_SIZE + CELL_BORDER
            for (gx, gy), (symbol, _) in pass_results.items():
                rel_x = (gx - start_x) * cell_total
                rel_y = (gy - start_y) * cell_total
                # Pass00 spécial : différencier unrevealed vs autres candidates
                if pass_name == "unrevealed_check":
                    if symbol == "unrevealed":
                        fill = (255, 80, 0, 160)  # orange vif : unrevealed confirmées
                    else:
                        fill = (255, 180, 120, 140)  # orange clair : autres candidates (non matchées)
                elif symbol.startswith("number_"):
                    number_colors = {
                        "number_1": (40, 120, 255, 160),
                        "number_2": (60, 200, 80, 160),
                        "number_3": (255, 80, 80, 180),
                        "number_4": (90, 0, 200, 170),
                        "number_5": (200, 40, 40, 180),
                        "number_6": (40, 180, 180, 170),
                        "number_7": (0, 0, 0, 180),
                        "number_8": (120, 120, 120, 180),
                    }
                    fill = number_colors.get(symbol, (70, 160, 255, 160))
                elif symbol == "exploded":
                    fill = (255, 0, 0, 190)  # rouge vif pour mines détectées
                elif symbol == "empty":
                    fill = (180, 255, 120, 150)
                elif symbol == "flag":
                    fill = (255, 80, 80, 160)
                else:
                    fill = (255, 200, 120, 140)
                draw.rectangle(
                    [(rel_x, rel_y), (rel_x + CELL_SIZE, rel_y + CELL_SIZE)], fill=fill
                )
            combined = Image.alpha_composite(base_image, overlay)
            filename = self._build_overlay_filename(
                screenshot_path,
                f"pass{pass_order:02d}_{pass_name}",
            )
            overlay_path = os.path.join(self.analysis_overlays_path, filename)
            os.makedirs(self.analysis_overlays_path, exist_ok=True)
            combined.convert("RGB").save(overlay_path, optimize=True)
            print(f"[OVERLAY] Passe {pass_name} sauvegardée: {overlay_path}")
            return overlay_path
        except Exception as e:
            print(f"[WARN] Impossible de générer l'overlay pour la passe {pass_name}: {e}")
            return None

    def _save_analysis_diff(
        self,
        filtering_info: Dict[str, Any],
        state_index: Dict[Tuple[int, int], Dict[str, Any]],
        grid_results: Dict[Tuple[int, int], Tuple[str, float]],
        bounds: Tuple[int, int, int, int],
        screenshot_name: str,
    ) -> Optional[str]:
        try:
            diff = []
            for coord, (symbol, confidence) in grid_results.items():
                old = state_index.get(coord, {})
                if old.get("type") != symbol:
                    diff.append(
                        {
                            "coordinates": coord,
                            "previous": old.get("type", "none"),
                            "current": symbol,
                            "confidence": float(confidence),
                        }
                    )
            filename = f"{screenshot_name}_analysis_diff.json"
            diff_path = os.path.join(self.analysis_overlays_path, filename)
            with open(diff_path, "w", encoding="utf-8") as f:
                json.dump(diff, f, indent=2, ensure_ascii=False)
            return diff_path
        except Exception as e:
            print(f"[WARN] Impossible de sauvegarder analysis_diff: {e}")
            return None

    def _fill_missing_results(
        self,
        grid_results: Dict[Tuple[int, int], Tuple[str, float]],
        state_index: Dict[Tuple[int, int], Dict[str, Any]],
        bounds: Tuple[int, int, int, int],
    ) -> Dict[Tuple[int, int], Tuple[str, float]]:
        start_x, start_y, end_x, end_y = bounds
        filled = dict(grid_results)
        for gx in range(start_x, end_x + 1):
            for gy in range(start_y, end_y + 1):
                coord = (gx, gy)
                if coord in filled:
                    continue
                previous = state_index.get(coord)
                if previous:
                    filled[coord] = (previous["type"], float(previous.get("confidence", 0.0)))
                else:
                    filled[coord] = ("unknown", 0.0)
        return filled

    def _run_logical_empty_inference(
        self,
        candidate_cells: List[Tuple[int, int]],
        zone_tuple: Tuple[int, int, int, int],
        state_index: Dict[Tuple[int, int], Dict[str, Any]],
        previous_pass_results: Optional[Dict[Tuple[int, int], Tuple[str, float]]],
    ) -> Dict[Tuple[int, int], Tuple[str, float]]:
        """
        Infère logiquement les cellules vides (EMPTY) basé sur leur connectivité 
        aux cellules UNREVEALED détectées dans pass00.
        
        Utilise un flood-fill BFS depuis les cellules UNREVEALED pour marquer
        toutes les cellules connectées. Les cellules candidates non connectées
        sont marquées comme EMPTY.
        """
        from collections import deque
        
        results: Dict[Tuple[int, int], Tuple[str, float]] = {}

        def _mark_empty_cells(cells: Iterable[Tuple[int, int]]) -> None:
            for coord in cells:
                gx, gy = coord
                self.grid_db.add_cell(
                    gx,
                    gy,
                    {
                        "type": "empty",
                        "confidence": 1.0,
                        "state": "TO_PROCESS",
                        "known": True,
                    },
                )
                results[coord] = ("empty", 1.0)
        
        # Filtrer les candidates pour exclure les cellules avec états connus non-vides
        candidate_set = set()
        for coord in candidate_cells:
            existing_state = state_index.get(coord, {})
            existing_type = existing_state.get("type", "unknown")
            # Ne considérer que les cellules inconnues ou potentiellement vides
            if existing_type in ["unknown", "empty", "unrevealed"]:
                candidate_set.add(coord)
        
        if not candidate_set:
            print("[INFO] Logical empty inference: aucune cellule candidate après filtrage")
            return results
        
        # Si pas de résultats précédents (pas de UNREVEALED détectées), considérer tout comme vide
        if not previous_pass_results:
            print("[INFO] Logical empty inference: aucun résultat pass00, marquage 100% EMPTY")
            _mark_empty_cells(candidate_set)
            return results
            
        # Extraire les cellules UNREVEALED de pass00
        unrevealed_cells = {
            coord for coord, (symbol, _) in previous_pass_results.items() if symbol == "unrevealed"
        }
        
        if not unrevealed_cells:
            print("[INFO] Logical empty inference: pass00 sans UNREVEALED, marquage 100% EMPTY")
            _mark_empty_cells(candidate_set)
            return results
            
        print(f"[INFO] Logical empty inference: {len(unrevealed_cells)} cellules UNREVEALED comme points de départ")
        print(f"[INFO] Logical empty inference: {len(candidate_set)} cellules candidates après filtrage")
        
        # Logique d'adjacence stricte (Flood-fill profondeur 1)
        # Dans le démineur :
        # - Les chiffres (Frontier) SONT adjacents aux cases non révélées (mines potentielles)
        # - Les cases vides (Interior) ne sont JAMAIS adjacentes aux cases non révélées (sinon auto-reveal)
        
        frontier_cells = set()
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        
        for u_coord in unrevealed_cells:
            gx, gy = u_coord
            for dx, dy in directions:
                neighbor = (gx + dx, gy + dy)
                if neighbor in candidate_set:
                    frontier_cells.add(neighbor)
        
        # Les cellules candidates qui ne touchent PAS de case unrevealed sont forcément EMPTY
        empty_cells = candidate_set - frontier_cells
        
        # Log de monitoring pour production
        print(
            f"[INFO] Logical empty inference: {len(frontier_cells)} Frontière (Chiffres/Décor), "
            f"{len(empty_cells)} Intérieur (EMPTY), {len(candidate_set)} Total candidates"
        )
        empty_ratio = (len(empty_cells) / len(candidate_set) * 100.0) if candidate_set else 0.0
        print(f"[INFO] Ratio: {empty_ratio:.1f}% des candidates marquées EMPTY")
        
        _mark_empty_cells(empty_cells)
        return results
