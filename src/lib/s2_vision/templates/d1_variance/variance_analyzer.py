#!/usr/bin/env python3
"""
Analyseur de variance simple pour visualiser la variation de chaque pixel par symbole.

Génère une heatmap par symbole montrant où les pixels varient le plus,
permettant d'observer la distance depuis le bord où il y a stabilité.
"""

import os
import json
import numpy as np
from PIL import Image
from typing import Dict, List, Tuple
from pathlib import Path


class SimpleVarianceAnalyzer:
    """Analyseur de variance simple pour visualisation."""
    
    def __init__(self, dataset_dir: str, results_dir: str):
        self.dataset_dir = Path(dataset_dir)
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
        
    def load_symbol_dataset(self) -> Dict[str, List[np.ndarray]]:
        """Charge tous les échantillons du dataset organisé par symbole."""
        dataset = {}
        
        if not self.dataset_dir.exists():
            raise FileNotFoundError(f"Dataset introuvable: {self.dataset_dir}")
        
        for symbol_dir in self.dataset_dir.iterdir():
            if not symbol_dir.is_dir():
                continue
                
            symbol_name = symbol_dir.name
            images = []
            
            for img_file in symbol_dir.glob("*.png"):
                try:
                    img = Image.open(img_file).convert("RGB")
                    img_array = np.array(img, dtype=np.uint8)
                    images.append(img_array)
                except Exception as e:
                    print(f"Erreur chargement {img_file}: {e}")
            
            if images:
                dataset[symbol_name] = images
                print(f"Chargé {len(images)} images pour '{symbol_name}'")
        
        return dataset
    
    def compute_variance_heatmap(self, images: List[np.ndarray]) -> np.ndarray:
        """
        Calcule la heatmap de variance pour un ensemble d'images.
        
        Args:
            images: Liste des arrays d'images (H×W×3)
            
        Returns:
            variance_map: Carte de variance RGB (H×W×3)
        """
        if not images:
            raise ValueError("Aucune image fournie")
        
        # Empiler toutes les images
        stacked = np.stack(images, axis=0)  # (N, H, W, 3)
        
        # Calculer variance par canal RGB
        variance_map = np.var(stacked, axis=0, dtype=np.float64)  # (H, W, 3)
        
        # Variance totale (moyenne des 3 canaux) pour visualisation
        variance_total = np.mean(variance_map, axis=2)  # (H, W)
        
        return variance_total
    
    def generate_heatmap(self, symbol_name: str, variance_map: np.ndarray):
        """
        Génère et sauvegarde la heatmap de variance pour un symbole en utilisant PIL.
        
        Args:
            symbol_name: Nom du symbole
            variance_map: Carte de variance totale (H×W)
        """
        # Normaliser la variance pour l'affichage (0-255)
        variance_min = np.min(variance_map)
        variance_max = np.max(variance_map)
        
        if variance_max > variance_min:
            variance_normalized = ((variance_map - variance_min) / (variance_max - variance_min) * 255).astype(np.uint8)
        else:
            variance_normalized = np.zeros_like(variance_map, dtype=np.uint8)
        
        # Créer une image en couleurs (heatmap)
        h, w = variance_normalized.shape
        heatmap_image = np.zeros((h, w, 3), dtype=np.uint8)
        
        # Appliquer une colormap simple (noir -> rouge -> jaune -> blanc)
        for i in range(h):
            for j in range(w):
                value = variance_normalized[i, j]
                if value < 64:
                    # Noir -> rouge
                    heatmap_image[i, j] = [value * 4, 0, 0]
                elif value < 128:
                    # Rouge -> jaune
                    t = (value - 64) / 64
                    heatmap_image[i, j] = [255, int(t * 255), 0]
                elif value < 192:
                    # Jaune -> blanc
                    t = (value - 128) / 64
                    heatmap_image[i, j] = [255, 255, int(t * 255)]
                else:
                    # Blanc
                    heatmap_image[i, j] = [255, 255, 255]
        
        # Convertir en image PIL
        pil_image = Image.fromarray(heatmap_image, 'RGB')
        
        # Sauvegarder
        output_path = self.results_dir / f'{symbol_name}_variance_heatmap.png'
        pil_image.save(output_path)
        
        print(f"Heatmap sauvegardée: {output_path}")
        print(f"  - Variance min: {variance_min:.1f}")
        print(f"  - Variance max: {variance_max:.1f}")
        
        return output_path
    
    def generate_superposed_heatmap(self, variance_maps: Dict[str, np.ndarray], 
                                 symbol_types: List[str]) -> np.ndarray:
        """
        Génère une heatmap superposée en faisant la moyenne des heatmaps de variance.
        
        Args:
            variance_maps: Dictionnaire des heatmaps de variance par symbole
            symbol_types: Liste des types de symboles à superposer
            
        Returns:
            superposed_variance: Carte de variance moyenne cumulée
        """
        print(f"\\nGénération heatmap superposée pour: {symbol_types}")
        
        # Récupérer les heatmaps de variance individuelles
        individual_variances = []
        for symbol_type in symbol_types:
            if symbol_type in variance_maps:
                individual_variances.append(variance_maps[symbol_type])
                print(f"  - {symbol_type}: heatmap ajoutée")
            else:
                print(f"  - {symbol_type}: non trouvée")
        
        if not individual_variances:
            raise ValueError("Aucune heatmap trouvée pour la superposition")
        
        # Calculer la moyenne élément par élément des heatmaps
        superposed_variance = np.mean(individual_variances, axis=0)
        
        print(f"Superposition de {len(individual_variances)} heatmaps")
        print(f"Variance moyenne superposée: {np.mean(superposed_variance):.1f}")
        
        return superposed_variance
    
    def analyze_optimal_margin(self, variance_map: np.ndarray, symbol_name: str = "") -> Dict:
        """
        Analyse la variance par distance depuis le bord pour déterminer la marge optimale.
        
        Args:
            variance_map: Heatmap de variance (H×W)
            symbol_name: Nom du symbole pour le logging
            
        Returns:
            Dictionnaire avec l'analyse de marge optimale
        """
        h, w = variance_map.shape
        
        # Analyser variance par distance depuis le bord
        distances = []
        variances = []
        
        max_distance = min(h, w) // 2
        for dist in range(max_distance):
            # Créer masque pour les pixels exactement à cette distance du bord
            mask = np.zeros_like(variance_map, dtype=bool)
            
            # Bords (distance max depuis centre)
            mask[:dist, :] = True  # Haut
            mask[-dist:, :] = True  # Bas
            mask[:, :dist] = True  # Gauche
            mask[:, -dist:] = True  # Droite
            
            # Exclure les distances intérieures pour n'avoir que l'anneau exact
            if dist > 0:
                inner_mask = np.zeros_like(variance_map, dtype=bool)
                inner_mask[:dist-1, :] = True
                inner_mask[-dist+1:, :] = True
                inner_mask[:, :dist-1] = True
                inner_mask[:, -dist+1:] = True
                mask = mask & ~inner_mask
            
            if np.any(mask):
                distances.append(dist)
                variances.append(np.mean(variance_map[mask]))
        
        # Calculer la variance de la région centrale (distance > 10)
        center_mask = np.zeros_like(variance_map, dtype=bool)
        center_margin = min(10, max_distance - 1)
        center_mask[center_margin:-center_margin, center_margin:-center_margin] = True
        center_variance = np.mean(variance_map[center_mask]) if np.any(center_mask) else 0
        
        # Déterminer la marge optimale
        # Seuil: variance < 2x variance centrale OU variance < 10% de la variance max
        variance_threshold1 = center_variance * 2.0
        variance_threshold2 = np.max(variances) * 0.1
        final_threshold = max(variance_threshold1, variance_threshold2)
        
        optimal_margin = 5  # Par défaut
        for dist, var in zip(distances, variances):
            if var <= final_threshold:
                optimal_margin = dist
                break
        
        # Afficher les résultats
        print(f"\\nAnalyse marge optimale{f' pour {symbol_name}' if symbol_name else ''}:")
        print(f"  Variance centrale: {center_variance:.1f}")
        print(f"  Seuil stabilisation: {final_threshold:.1f}")
        print(f"  Marge recommandée: {optimal_margin}px")
        
        # Afficher les détails par distance
        print("  Variance par distance:")
        for dist, var in zip(distances[:12], variances[:12]):  # Premier 12px
            status = "✓" if var <= final_threshold else "✗"
            print(f"    {dist}px: {var:6.1f} {status}")
        
        return {
            "optimal_margin": optimal_margin,
            "center_variance": center_variance,
            "threshold_used": final_threshold,
            "distance_analysis": list(zip(distances, variances)),
            "recommendation": f"Utiliser une marge de {optimal_margin}px pour éviter les éclats de mines"
        }
    
    def generate_annotated_heatmap(self, variance_map: np.ndarray, optimal_margin: int, symbol_name: str):
        """
        Génère une heatmap avec des annotations de distance pour validation visuelle.
        
        Args:
            variance_map: Heatmap de variance (H×W)
            optimal_margin: Marge optimale déterminée
            symbol_name: Nom du symbole
        """
        # Normaliser la variance pour l'affichage
        variance_min = np.min(variance_map)
        variance_max = np.max(variance_map)
        
        if variance_max > variance_min:
            variance_normalized = ((variance_map - variance_min) / (variance_max - variance_min) * 255).astype(np.uint8)
        else:
            variance_normalized = np.zeros_like(variance_map, dtype=np.uint8)
        
        # Créer l'image en couleurs
        h, w = variance_normalized.shape
        heatmap_image = np.zeros((h, w, 3), dtype=np.uint8)
        
        for i in range(h):
            for j in range(w):
                value = variance_normalized[i, j]
                if value < 64:
                    heatmap_image[i, j] = [value * 4, 0, 0]
                elif value < 128:
                    t = (value - 64) / 64
                    heatmap_image[i, j] = [255, int(t * 255), 0]
                elif value < 192:
                    t = (value - 128) / 64
                    heatmap_image[i, j] = [255, 255, int(t * 255)]
                else:
                    heatmap_image[i, j] = [255, 255, 255]
        
        # Convertir en image PIL
        pil_image = Image.fromarray(heatmap_image, 'RGB')
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(pil_image)
        
        # Dessiner les cercles concentriques pour les marges
        center_y, center_x = h // 2, w // 2
        
        # Marges importantes à visualiser
        margins_to_draw = [5, 7, 8, 9, optimal_margin]
        colors = [(255, 255, 0), (0, 255, 255), (255, 0, 255), (0, 255, 0), (255, 255, 255)]
        
        for margin, color in zip(margins_to_draw, colors):
            if margin < min(h, w) // 2:
                # Rectangle pour la marge (sans étiquette)
                draw.rectangle([margin, margin, w-margin-1, h-margin-1], 
                             outline=color, width=2)
        
        # Mettre en évidence la marge optimale
        draw.rectangle([optimal_margin, optimal_margin, w-optimal_margin-1, h-optimal_margin-1], 
                      outline=(255, 255, 255), width=3)
        
        # Sauvegarder
        output_path = self.results_dir / f'{symbol_name}_annotated_margin.png'
        pil_image.save(output_path)
        
        print(f"Heatmap annotée sauvegardée: {output_path}")
        return output_path
    
    def analyze_all_symbols(self):
        """Génère les heatmaps pour tous les symboles du dataset."""
        print("Chargement du dataset...")
        dataset = self.load_symbol_dataset()
        
        if not dataset:
            raise ValueError("Aucune donnée trouvée dans le dataset")
        
        results = {}
        variance_maps = {}  # Stocker les heatmaps de variance pour superposition
        
        for symbol_name, images in dataset.items():
            print(f"\\nGénération heatmap pour '{symbol_name}' ({len(images)} images)...")
            
            # Calculer variance
            variance_map = self.compute_variance_heatmap(images)
            
            # Stocker la heatmap pour superposition ultérieure
            variance_maps[symbol_name] = variance_map
            
            # Générer heatmap visuelle
            heatmap_path = self.generate_heatmap(symbol_name, variance_map)
            
            # Stocker résultats simples
            results[symbol_name] = {
                "image_count": len(images),
                "heatmap_file": str(heatmap_path),
                "variance_stats": {
                    "mean": float(np.mean(variance_map)),
                    "std": float(np.std(variance_map)),
                    "min": float(np.min(variance_map)),
                    "max": float(np.max(variance_map))
                },
                "image_shape": images[0].shape if images else None
            }
            
            print(f"  - Variance moyenne: {np.mean(variance_map):.1f}")
            print(f"  - Variance max: {np.max(variance_map):.1f}")
        
        # Sauvegarder résultats JSON
        results_path = self.results_dir / 'simple_variance_results.json'
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\\nRésultats sauvegardés: {results_path}")
        
        # Générer la heatmap superposée des nombres et cases vides
        print("\\n=== GÉNÉRATION HEATMAP SUPERPOSÉE ===")
        
        # Identifier tous les symboles de type "number_*" et "empty"
        number_symbols = [k for k in variance_maps.keys() if k.startswith('number_')]
        superposed_symbols = number_symbols + ['empty'] if 'empty' in variance_maps else number_symbols
        
        if superposed_symbols:
            print(f"Symboles pour superposition: {superposed_symbols}")
            
            # Générer la variance superposée à partir des heatmaps
            superposed_variance = self.generate_superposed_heatmap(variance_maps, superposed_symbols)
            
            # Générer et sauvegarder la heatmap superposée
            superposed_path = self.generate_heatmap("superposed_numbers_empty", superposed_variance)
            
            # ANALYSE DE LA MARGE OPTIMALE
            print("\\n=== ANALYSE MARGE OPTIMALE ===")
            margin_analysis = self.analyze_optimal_margin(superposed_variance, "superposed_numbers_empty")
            
            # Générer la heatmap annotée avec les marges
            annotated_path = self.generate_annotated_heatmap(superposed_variance, margin_analysis["optimal_margin"], "superposed_numbers_empty")
            
            # Ajouter aux résultats
            results["superposed_numbers_empty"] = {
                "image_count": sum(len(dataset.get(s, [])) for s in superposed_symbols),
                "heatmap_file": str(superposed_path),
                "annotated_heatmap_file": str(annotated_path),
                "variance_stats": {
                    "mean": float(np.mean(superposed_variance)),
                    "std": float(np.std(superposed_variance)),
                    "min": float(np.min(superposed_variance)),
                    "max": float(np.max(superposed_variance))
                },
                "image_shape": superposed_variance.shape + (3,) if len(superposed_variance.shape) == 2 else superposed_variance.shape,
                "combined_symbols": superposed_symbols,
                "method": "heatmap_superposition",
                "margin_analysis": margin_analysis
            }
            
            print(f"\\n✓ Heatmap superposée générée: {superposed_path}")
            print(f"✓ Heatmap annotée générée: {annotated_path}")
            print(f"✓ Marge optimale déterminée: {margin_analysis['optimal_margin']}px")
            print(f"\\nCONCLUSION FINALE:")
            print(f"  → Pour les chiffres et cases vides, utiliser une marge de {margin_analysis['optimal_margin']}px")
            print(f"  → Cette marge évite {len(superposed_symbols)} types de symboles des éclats de mines")
        else:
            print("⚠ Aucun symbole 'number_*' ou 'empty' trouvé pour la superposition")
        
        return results


def main():
    """Point d'entrée principal."""
    
    # Configuration
    current_dir = Path(__file__).parent
    dataset_dir = current_dir / "data_set"
    results_dir = current_dir / "variance_results"
    
    print("=== Générateur Simple de Heatmaps de Variance ===")
    print(f"Dataset: {dataset_dir}")
    print(f"Résultats: {results_dir}")
    print()
    
    try:
        # Créer l'analyseur
        analyzer = SimpleVarianceAnalyzer(str(dataset_dir), str(results_dir))
        
        # Analyser tous les symboles
        results = analyzer.analyze_all_symbols()
        
        # Résumé
        print("\\n=== RÉSUMÉ ===")
        print(f"Symboles analysés: {len(results)}")
        for symbol, info in results.items():
            print(f"  {symbol}: {info['image_count']} images, variance max: {info['variance_stats']['max']:.1f}")
        
    except Exception as e:
        print(f"Erreur: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
