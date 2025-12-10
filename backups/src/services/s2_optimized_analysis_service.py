"""
Service d'analyse optimisé avec template matching fixe
Version simplifiée sans fichiers temporaires
"""

import os
import time
import glob
from typing import Dict, Any, Optional, Tuple
from PIL import Image

from lib.s2_analysis.grid_state import GamePersistence, GridDB
from lib.s2_analysis.template_matching_fixed import FixedTemplateMatcher, build_grid_analysis_from_results
from lib.s2_analysis.mapper import VisionToGameMapper
from lib.config import PATHS


class OptimizedAnalysisService:
    """Service d'analyse optimisé avec template matching fixe"""

    def __init__(self, generate_overlays=True, paths: Dict[str, str] = None):
        """
        Initialise le service optimisé avec template matching
        
        Args:
            generate_overlays: Générer les overlays (peut être désactivé pour vitesse)
            paths: Chemins personnalisés pour les fichiers (obligatoire)
        """
        # Utiliser systématiquement le template matching fixe
        self.template_matcher = FixedTemplateMatcher("assets/symbols")
        self.generate_overlays = generate_overlays
        self.paths = paths or PATHS
        
        # GridDB avec chemin obligatoire
        grid_db_path = self.paths.get('grid_db')
        if not grid_db_path:
            raise ValueError("grid_db est obligatoire dans paths pour OptimizedAnalysisService")
        self.grid_db = GridDB(db_path=grid_db_path)
        
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
            from lib.s3_solver.visualization.solver_overlay_generator import SolverOverlayGenerator
            solver_dir = self.paths.get('solver')
            if not solver_dir:
                raise ValueError("solver est obligatoire dans paths pour OptimizedAnalysisService")
            self.overlay_generator = SolverOverlayGenerator(output_dir=solver_dir)
        else:
            self.overlay_generator = None

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
            
            # Utiliser le template matcher avec les coordonnées fournies
            grid_results = self.template_matcher.recognize_grid(screenshot_path, zone_bounds)
            if not grid_results:
                return {
                    'success': False,
                    'message': 'Aucune cellule détectée par template matching',
                    'cell_count': 0,
                    'performance': {'total_time': time.time() - start_time}
                }
            
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
            
            # Mettre à jour la DB GridDB
            self.grid_db.clear_all()  # Vider avant de remplir
            for (x, y), analysis in grid_analysis.cells.items():
                game_symbol = VisionToGameMapper.map_cell_type(analysis.cell_type)
                # Convertir CellSymbol en string pour GridDB
                cell_type = game_symbol.value
                self.grid_db.add_cell(x, y, {
                    "type": cell_type,
                    "confidence": analysis.confidence,
                    "state": "TO_PROCESS"
                })
            
            # Sauvegarder la DB
            self.grid_db.flush_to_disk()
            
            # Générer les overlays si demandé
            overlay_paths = []
            should_generate = generate_overlays if generate_overlays is not None else self.generate_overlays
            
            # Désactivé - l'overlay est généré par s3_game_solver_service avec la bonne nomenclature
            # if should_generate and self.overlay_generator:
            #     overlay_start = time.time()
            #     overlay_path = self.overlay_generator.generate_overlay_from_db(
            #         screenshot_path, self.grid_db
            #     )
            #     overlay_paths = [overlay_path] if overlay_path else []
            #     overlay_time = time.time() - overlay_start
            #     print(f"[INFO] Overlay généré en {overlay_time:.2f}s")
            
            overlay_paths = []  # Pas d'overlay généré ici
            
            # Calculer les statistiques de performance
            total_time = time.time() - start_time
            
            result = {
                'success': True,
                'filename': filename,
                'path': screenshot_path,
                'grid_bounds': (start_x, start_y, end_x, end_y),  # Coordonnées absolues
                'cell_count': len(grid_analysis.cells),
                'overlay_paths': overlay_paths,
                'overlay_path': overlay_paths[0] if overlay_paths else None,
                'performance': {
                    'total_time': total_time,
                    'cells_per_second': len(grid_analysis.cells) / total_time if total_time > 0 else 0,
                    'cache_stats': {'template_matching': True}
                }
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
