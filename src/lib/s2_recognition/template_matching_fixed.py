#!/usr/bin/env python3
"""
Demo corrigé du template matching
Utilise une méthode hybride: corrélation pour les images variées, différence pour les uniformes
"""

import json
import os
import sys
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Tuple, List, Any, Optional
import time
from datetime import datetime

try:
    import cv2
except ImportError:
    cv2 = None

# Ajouter le répertoire racine au PYTHONPATH pour les imports relatifs
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lib.s3_tensor.types import CellType, CellAnalysis, GridAnalysis

# Configuration
SCREENSHOTS_DIR = "temp/screenshots/zones"
OVERLAYS_DIR = "temp/analysis/overlays"
TEMPLATES_DIR = "src/lib/s2_recognition/s21_templates/symbols"

# Mapping des templates
TEMPLATE_MAPPING = {
    '1.png': 'number_1',
    '2.png': 'number_2', 
    '3.png': 'number_3',
    '4.png': 'number_4',
    '5.png': 'number_5',
    '6.png': 'number_6',
    '7.png': 'number_7',
    'Flag.png': 'flag',
    'inactive.png': 'unrevealed',
    'vide.png': 'empty',
    'exploded.png': 'exploded',
    'exploded_a.png': 'exploded',
}

# Configuration des cellules
from src.lib.config import CELL_SIZE, CELL_BORDER
EXPLODED_MIN_CONFIDENCE = 0.1
NUMBER_MIN_CONFIDENCE = 0.5

class FixedTemplateMatcher:
    """Moteur de reconnaissance par template matching (version corrigée)"""
    
    def __init__(
        self,
        templates_dir: str,
        prefer_backend: str = "auto",
        shadow_compare: bool = False,
    ):
        self.templates_dir = templates_dir
        self.templates = {}
        self.template_images = {}
        self.template_metadata: Dict[str, Dict[str, Any]] = {}
        backend_pref = os.environ.get("S2_TM_BACKEND", prefer_backend).strip().lower()
        self.shadow_compare = shadow_compare or os.environ.get("S2_TM_SHADOW_HYBRID", "0") == "1"
        self.backend = self._select_backend(backend_pref)
        self.shadow_stats = {"total": 0, "divergent": 0}
        self.match_stats = {
            "backend": self.backend,
            "total_calls": 0,
            "opencv_primary": 0,
            "hybrid_primary": 0,
            "fallback_used": 0,
        }
        self._load_template_manifest()
        self.load_templates()
        print(
            f"[INFO] FixedTemplateMatcher backend sélectionné: {self.backend.upper()} "
            f"(shadow={'ON' if self.shadow_compare else 'OFF'})"
        )

    def _select_backend(self, backend_pref: str) -> str:
        if backend_pref == "opencv":
            if cv2 is not None:
                return "opencv"
            print("[WARN] Backend OpenCV demandé mais indisponible, fallback HYBRID")
            return "hybrid"
        if backend_pref == "hybrid":
            return "hybrid"
        # Mode auto
        if cv2 is not None:
            return "opencv"
        return "hybrid"

    def _load_template_manifest(self) -> None:
        """Charge le manifeste généré par build_template_manifest."""
        manifest_path = Path(self.templates_dir).parent / "template_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.template_metadata = data.get("templates", {})
                print(f"[CHARGEMENT] Manifestes templates: {len(self.template_metadata)} entrées")
            except Exception as exc:
                print(f"[WARN] Impossible de lire le manifeste des templates: {exc}")
                self.template_metadata = {}
        else:
            print(f"[INFO] Aucun manifeste trouvé à {manifest_path}, utilisation du comportement par défaut")
            self.template_metadata = {}
    
    def load_templates(self):
        """Charge tous les templates depuis le dossier src/lib/s2_recognition/s21_templates/symbols"""
        print(f"[CHARGEMENT] Templates depuis {self.templates_dir}")
        
        if not os.path.exists(self.templates_dir):
            print(f"[ERREUR] Dossier templates non trouvé: {self.templates_dir}")
            return
        
        for filename, symbol_name in TEMPLATE_MAPPING.items():
            template_path = os.path.join(self.templates_dir, filename)
            if os.path.exists(template_path):
                # Charger avec PIL et convertir en numpy array
                template_pil = Image.open(template_path).convert('L')  # Niveaux de gris
                template_np = np.array(template_pil, dtype=np.float32)
                
                self.template_images[symbol_name] = template_np
                self.templates[symbol_name] = filename
                print(f"  [OK] {symbol_name} <- {filename} (taille: {template_np.shape})")
            else:
                print(f"  [ERREUR] Manquant: {filename}")
        
        print(f"[INFO] {len(self.template_images)} templates chargés")
    
    def match_cell_hybrid(
        self, cell_image: np.ndarray, allowed_symbols: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        """
        Reconnaît une cellule par template matching hybride
        
        Args:
            cell_image: Image de la cellule en niveaux de gris
            
        Returns:
            Tuple[symbol, confidence]: Symbole reconnu et confiance
        """
        if not self.template_images:
            return "UNKNOWN", 0.0
        
        best_match = "UNKNOWN"
        best_score = 0.0
        best_method = "none"
        
        # Convertir en float32 pour les calculs
        cell_float = cell_image.astype(np.float32)
        
        # Vérifier si la cellule est uniforme
        cell_std = np.std(cell_float)
        is_cell_uniform = cell_std < 0.001
        
        # Tester tous les templates
        symbols_to_match = (
            allowed_symbols if allowed_symbols else list(self.template_images.keys())
        )

        for symbol_name in symbols_to_match:
            template = self.template_images.get(symbol_name)
            if template is None:
                continue
            # Vérifier si le template est uniforme
            template_std = np.std(template)
            is_template_uniform = template_std < 0.001
            
            # Choisir la méthode de matching
            if is_cell_uniform and is_template_uniform:
                # Méthode 1: Différence absolue moyenne pour images uniformes
                diff = np.abs(cell_float - template)
                score = 1.0 - (diff.mean() / 255.0)  # Normaliser entre 0 et 1
                method = "uniform_diff"
            elif not is_cell_uniform and not is_template_uniform:
                # Méthode 2: Corrélation normalisée pour images variées
                # Normaliser les deux images
                cell_norm = (cell_float - np.mean(cell_float)) / (np.std(cell_float) + 1e-8)
                template_norm = (template - np.mean(template)) / (np.std(template) + 1e-8)
                
                # Calculer la corrélation
                correlation = np.sum(cell_norm * template_norm) / (cell_norm.shape[0] * cell_norm.shape[1])
                score = abs(correlation)  # Prendre la valeur absolue
                method = "correlation"
            else:
                # Méthode 3: Différence simple pour cas mixtes
                diff = np.abs(cell_float - template)
                score = 1.0 - (diff.mean() / 255.0)
                method = "mixed_diff"
            
            if score > best_score:
                best_score = score
                best_match = symbol_name
                best_method = method
        
        # Ajuster la confiance selon la méthode
        if best_method == "uniform_diff":
            confidence = best_score
        elif best_method == "correlation":
            confidence = best_score
        else:
            confidence = best_score * 0.8
        
        if confidence > 0.8:
            return best_match, confidence
        elif confidence > 0.5:
            return best_match, confidence * 0.9
        elif confidence > 0.3:
            return best_match, confidence * 0.7
        else:
            return "UNKNOWN", 0.0

    def _match_cell_opencv(
        self, cell_image: np.ndarray, allowed_symbols: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        if cv2 is None:
            return "UNKNOWN", 0.0
        cell = cell_image.astype(np.float32)
        best_match = "UNKNOWN"
        best_score = -1.0
        symbols_to_match = (
            allowed_symbols if allowed_symbols else list(self.template_images.keys())
        )
        for symbol_name in symbols_to_match:
            template = self.template_images.get(symbol_name)
            if template is None:
                continue
            result = cv2.matchTemplate(cell, template, cv2.TM_CCOEFF_NORMED)
            score = float(result[0][0])
            if score > best_score:
                best_score = score
                best_match = symbol_name
        if best_score < 0.65:
            return "UNKNOWN", 0.0
        if best_score >= 0.92:
            confidence = best_score
        elif best_score >= 0.85:
            confidence = best_score * 0.98
        elif best_score >= 0.75:
            confidence = best_score * 0.9
        else:
            return "UNKNOWN", 0.0
        return best_match, confidence

    def match_cell(
        self, cell_image: np.ndarray, allowed_symbols: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        self.match_stats["total_calls"] += 1
        if self.backend == "opencv" and cv2 is not None:
            self.match_stats["opencv_primary"] += 1
            symbol, confidence = self._match_cell_opencv(cell_image, allowed_symbols)
            if symbol == "UNKNOWN":
                fallback_symbol, fallback_conf = self.match_cell_hybrid(
                    cell_image, allowed_symbols
                )
                if fallback_symbol != "UNKNOWN":
                    print("[INFO] Fallback HYBRID utilisé pour une cellule non reconnue par OpenCV")
                    self.match_stats["fallback_used"] += 1
                return fallback_symbol, fallback_conf
            if self.shadow_compare:
                self._shadow_compare(symbol, confidence, cell_image, allowed_symbols)
            return symbol, confidence
        self.match_stats["hybrid_primary"] += 1
        return self.match_cell_hybrid(cell_image, allowed_symbols)

    def _shadow_compare(
        self,
        primary_symbol: str,
        primary_confidence: float,
        cell_image: np.ndarray,
        allowed_symbols: Optional[List[str]],
    ) -> None:
        try:
            shadow_symbol, shadow_confidence = self.match_cell_hybrid(
                cell_image, allowed_symbols
            )
            self.shadow_stats["total"] += 1
            if shadow_symbol != primary_symbol:
                self.shadow_stats["divergent"] += 1
                if self.shadow_stats["divergent"] <= 5:
                    print(
                        f"[SHADOW] Divergence #{self.shadow_stats['divergent']}: "
                        f"{primary_symbol} ({primary_confidence:.3f}) vs "
                        f"{shadow_symbol} ({shadow_confidence:.3f})"
                    )
                elif self.shadow_stats["divergent"] % 50 == 0:
                    print(
                        f"[SHADOW] {self.shadow_stats['divergent']} divergences "
                        f"sur {self.shadow_stats['total']} comparaisons"
                    )
        except Exception as exc:
            print(f"[SHADOW] Erreur comparaison hybride: {exc}")
    
    def get_runtime_stats(self) -> Dict[str, Any]:
        """Expose des métriques runtime pour monitoring en production."""
        stats = dict(self.match_stats)
        stats.update(
            {
                "shadow_total": self.shadow_stats["total"],
                "shadow_divergent": self.shadow_stats["divergent"],
                "shadow_ratio": (
                    self.shadow_stats["divergent"] / self.shadow_stats["total"]
                    if self.shadow_stats["total"] > 0
                    else 0.0
                ),
            }
        )
        return stats

    def _allowed_symbols_for_pass(self, pass_name: str) -> Optional[List[str]]:
        if pass_name == "unrevealed_check":
            return ["unrevealed"]
        if pass_name == "empty_refresh":
            return ["empty"]
        if pass_name == "exploded_check":
            return ["exploded"]
        if pass_name == "numbers_refresh":
            symbols = [f"number_{i}" for i in range(1, 9)]
            symbols.append("exploded")
            return symbols
        # None => tous les symboles autorisés
        return None

    def _get_template_stats(self, symbol: str) -> Dict[str, Any]:
        return self.template_metadata.get(symbol, {})

    def match_template_at(
        self, image_np: np.ndarray, center_x: float, center_y: float, pass_name: str
    ) -> Optional[Tuple[str, float]]:
        """
        Extrait la cellule centrée sur (center_x, center_y) et lance un matching
        limité aux symboles pertinents pour la passe courante.
        """
        half_size = CELL_SIZE // 2
        left = int(center_x - half_size)
        top = int(center_y - half_size)
        right = left + CELL_SIZE
        bottom = top + CELL_SIZE

        if (
            left < 0
            or top < 0
            or right > image_np.shape[1]
            or bottom > image_np.shape[0]
        ):
            return None

        cell_image = image_np[top:bottom, left:right]
        if cell_image.shape != (CELL_SIZE, CELL_SIZE):
            return None

        if pass_name in {"unrevealed_check", "empty_refresh"}:
            symbol_ref = "unrevealed" if pass_name == "unrevealed_check" else "empty"
            stats = self._get_template_stats(symbol_ref)
            cell_mean = float(cell_image.mean())
            cell_std = float(cell_image.std())
            if stats:
                mean_ref = stats.get("mean", cell_mean)
                std_ref = stats.get("std", cell_std)
                tolerance_mean = max(3.0, 0.02 * mean_ref)
                tolerance_std = max(2.0, 0.5 * std_ref + 1.0)
                if abs(cell_mean - mean_ref) > tolerance_mean or cell_std > std_ref + tolerance_std:
                    return None
            else:
                # Fallback heuristique si pas de manifeste
                if pass_name == "unrevealed_check":
                    if cell_mean < 235.0 or cell_std > 5.0:
                        return None
                else:  # empty_refresh
                    if not (150.0 <= cell_mean <= 220.0) or cell_std > 15.0:
                        return None

        allowed = self._allowed_symbols_for_pass(pass_name)
        symbol, confidence = self.match_cell(cell_image, allowed_symbols=allowed)
        if symbol == "UNKNOWN":
            return None
        # Seuils additionnels
        if pass_name == "unrevealed_check" and confidence < 0.75:
            return None
        if symbol.startswith("number_") and confidence < NUMBER_MIN_CONFIDENCE:
            return None
        if symbol == "exploded" and confidence < EXPLODED_MIN_CONFIDENCE:
            return None
        return symbol, confidence
    
    def recognize_grid(self, image_path: str, zone_bounds: Optional[Tuple[int, int, int, int]] = None) -> Dict[Tuple[int, int], Tuple[str, float]]:
        """
        Reconnaît toute la grille d'un screenshot
        
        Args:
            image_path: Chemin du screenshot à analyser
            zone_bounds: Coordonnées (start_x, start_y, end_x, end_y) si non présentes dans le nom
            
        Returns:
            Dict[(x, y), (symbol, confidence)]: Résultats par coordonnées
        """
        print(f"[ANALYSE] {os.path.basename(image_path)}")
        
        # Charger l'image
        image_pil = Image.open(image_path).convert('L')  # Niveaux de gris
        image_np = np.array(image_pil, dtype=np.float32)
        
        # Extraire les coordonnées depuis le nom du fichier ou les paramètres
        filename = os.path.basename(image_path)
        
        if zone_bounds:
            start_x, start_y, end_x, end_y = zone_bounds
            print(f"[DEBUG] Utilisation coordonnées fournies: {zone_bounds}")
        else:
            # Parser le nom du fichier (format legacy)
            parts = filename.replace('zone_', '').split('_')
            if len(parts) < 5:
                print(f"[ERREUR] Format de fichier non reconnu: {filename}")
                return {}
            
            try:
                start_x = int(parts[0])
                start_y = int(parts[1])
                end_x = int(parts[2])
                end_y = int(parts[3])
            except ValueError:
                print(f"[ERREUR] Coordonnées invalides dans: {filename}")
                return {}
        
        # Reconnaître chaque cellule
        results = {}
        cell_count = 0
        stats = {"UNKNOWN": 0, "unrevealed": 0, "empty": 0}
        
        for x in range(start_x, end_x + 1):
            for y in range(start_y, end_y + 1):
                # Calculer les coordonnées pixel de la cellule
                pixel_x = (x - start_x) * (CELL_SIZE + CELL_BORDER)
                pixel_y = (y - start_y) * (CELL_SIZE + CELL_BORDER)
                
                # Extraire la cellule
                cell_image = image_np[pixel_y:pixel_y+CELL_SIZE, pixel_x:pixel_x+CELL_SIZE]
                
                if cell_image.size == 0:
                    continue
                
                # Reconnaître la cellule
                symbol, confidence = self.match_cell(cell_image)
                results[(x, y)] = (symbol, confidence)
                cell_count += 1
                
                # Statistiques
                stats[symbol] = stats.get(symbol, 0) + 1
        
        print(f"[SUCCES] {cell_count} cellules analysées")
        print(f"[STATS] {stats}")
        return results

def build_grid_analysis_from_results(
    image_path: str,
    results: Dict[Tuple[int, int], Tuple[str, float]],
    zone_bounds: Optional[Tuple[int, int, int, int]] = None
) -> GridAnalysis:
    """Construit un GridAnalysis compatible à partir des résultats de template matching."""
    filename = os.path.basename(image_path)
    
    if zone_bounds:
        start_x, start_y, end_x, end_y = zone_bounds
    else:
        # Parser le nom du fichier (format legacy)
        parts = filename.replace("zone_", "").split("_")
        start_x = int(parts[0])
        start_y = int(parts[1])
        end_x = int(parts[2])
        end_y = int(parts[3])

    cells: Dict[Tuple[int, int], CellAnalysis] = {}

    def to_cell_type(symbol: str) -> CellType:
        mapping = {
            'empty': CellType.EMPTY,
            'unrevealed': CellType.UNREVEALED,
            'flag': CellType.FLAG,
            'mine': CellType.MINE,
            'exploded': CellType.MINE,
            'number_1': CellType.NUMBER_1,
            'number_2': CellType.NUMBER_2,
            'number_3': CellType.NUMBER_3,
            'number_4': CellType.NUMBER_4,
            'number_5': CellType.NUMBER_5,
            'number_6': CellType.NUMBER_6,
            'number_7': CellType.NUMBER_7,
            'number_8': CellType.NUMBER_8,
        }
        return mapping.get(symbol, CellType.UNKNOWN)

    for (x, y), (symbol, confidence) in results.items():
        cell_type = to_cell_type(symbol)
        analysis = CellAnalysis(
            coordinates=(x, y),
            cell_type=cell_type,
            confidence=float(confidence),
            colors=[],
            raw_image=None,
        )
        cells[(x, y)] = analysis

    grid_bounds = (start_x, start_y, end_x, end_y)
    return GridAnalysis(grid_bounds=grid_bounds, cells=cells)

def main():
    """Fonction principale de démonstration"""
    print("=" * 60)
    print("DEMO TEMPLATE MATCHING CORRIGÉ")
    print("=" * 60)
    
    # Vérifier les dossiers
    if not os.path.exists(SCREENSHOTS_DIR):
        print(f"[ERREUR] Dossier screenshots non trouvé: {SCREENSHOTS_DIR}")
        return
    
    if not os.path.exists(TEMPLATES_DIR):
        print(f"[ERREUR] Dossier templates non trouvé: {TEMPLATES_DIR}")
        return
    
    # Initialiser les composants
    matcher = FixedTemplateMatcher(TEMPLATES_DIR)
    # overlay_gen = OptimizedOverlayGenerator(cell_size=CELL_SIZE, output_dir=OVERLAYS_DIR) # Plus utilisé
    
    if not matcher.template_images:
        print("[ERREUR] Aucun template chargé, impossible de continuer")
        return
    
    # Lister les screenshots
    screenshots = [f for f in os.listdir(SCREENSHOTS_DIR) if f.endswith('.png')]
    print(f"[INFO] {len(screenshots)} screenshots trouvés")
    
    # Analyser chaque screenshot (limité pour la démo pour éviter les runs trop longs)
    MAX_SCREENSHOTS = 5
    total_cells = 0
    total_time = 0

    for screenshot in screenshots[:MAX_SCREENSHOTS]:
        screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot)

        start_time = time.time()
        
        # Charger l'image couleur pour l'overlay
        grid_image_color = Image.open(screenshot_path).convert('RGB')

        # Reconnaissance (travaille en niveaux de gris en interne)
        results = matcher.recognize_grid(screenshot_path)

        # Construire un GridAnalysis et générer l'overlay optimisé
        if results:
            grid_analysis = build_grid_analysis_from_results(screenshot_path, results)
            # overlay_path = overlay_gen.generate_recognition_overlay_optimized(
            #     grid_image_color, grid_analysis, screenshot_file=screenshot
            # ) # Plus utilisé
            total_cells += len(results)
        
        elapsed = time.time() - start_time
        total_time += elapsed
        
        print(f"[TEMPS] {screenshot}: {elapsed:.2f}s ({len(results)} cellules)")
        
        # Afficher quelques résultats avec confiance
        if results:
            sample_results = list(results.items())[:5]
            print(f"[EXEMPLES] {sample_results}")
    
    # Statistiques finales
    print("\n" + "=" * 60)
    print("STATISTIQUES")
    print("=" * 60)
    print(f"Cellules analysées: {total_cells}")
    print(f"Temps total: {total_time:.2f}s")
    if total_cells > 0:
        print(f"Vitesse: {total_cells/total_time:.1f} cellules/seconde")
    # print(f"Overlays générés: {len(os.listdir(OVERLAYS_DIR))}") # Plus utilisé
    
    # Comparaison avec méthode actuelle
    print(f"\n[COMPARAISON] Vitesse actuelle: ~20 cellules/seconde")
    print(f"[COMPARAISON] Template matching corrigé: {total_cells/total_time:.1f} cellules/seconde")
    print(f"[AMÉLIORATION] {(total_cells/total_time)/20:.1f}x plus rapide")

if __name__ == "__main__":
    main()
