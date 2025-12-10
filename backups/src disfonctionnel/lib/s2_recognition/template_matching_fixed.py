#!/usr/bin/env python3
"""
Demo corrigé du template matching
Utilise une méthode hybride: corrélation pour les images variées, différence pour les uniformes
"""

import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Tuple, List, Any
import time
from datetime import datetime

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
    'vide.png': 'empty'
}

# Configuration des cellules
CELL_SIZE = 24
CELL_BORDER = 1

class FixedTemplateMatcher:
    """Moteur de reconnaissance par template matching (version corrigée)"""
    
    def __init__(self, templates_dir: str):
        self.templates_dir = templates_dir
        self.templates = {}
        self.template_images = {}
        self.load_templates()
    
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
    
    def match_cell_hybrid(self, cell_image: np.ndarray) -> Tuple[str, float]:
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
        for symbol_name, template in self.template_images.items():
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
            # Très fiable pour les images uniformes
            confidence = best_score
        elif best_method == "correlation":
            # Fiable pour les images variées
            confidence = best_score
        else:
            # Moins fiable pour les cas mixtes
            confidence = best_score * 0.8
        
        # Seuils adaptatifs
        if confidence > 0.8:
            return best_match, confidence  # Très bon match
        elif confidence > 0.5:
            return best_match, confidence * 0.9  # Bon match
        elif confidence > 0.3:
            return best_match, confidence * 0.7  # Match partiel
        else:
            return "UNKNOWN", 0.0  # Pas de match
    
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
                symbol, confidence = self.match_cell_hybrid(cell_image)
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
