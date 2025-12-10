#!/usr/bin/env python3
"""
Vérifie les templates pour comprendre pourquoi unrevealed ne matche pas
"""

import os
import numpy as np
from PIL import Image

TEMPLATES_DIR = "assets/symbols"

def analyze_templates():
    """Analyse tous les templates"""
    print("ANALYSE DES TEMPLATES")
    print("=" * 50)
    
    for filename in os.listdir(TEMPLATES_DIR):
        if filename.endswith('.png'):
            template_path = os.path.join(TEMPLATES_DIR, filename)
            template_pil = Image.open(template_path).convert('L')
            template_np = np.array(template_pil, dtype=np.float32)
            
            print(f"\n{filename}:")
            print(f"  Taille: {template_np.shape}")
            print(f"  Min/Max: {template_np.min():.1f} / {template_np.max():.1f}")
            print(f"  Moyenne: {template_np.mean():.1f}")
            print(f"  Écart-type: {template_np.std():.3f}")
            
            # Afficher quelques valeurs
            values = template_np.flatten()[:10]
            print(f"  Valeurs: {values}")
            
            # Vérifier si c'est uniforme
            if template_np.std() < 0.001:
                print(f"  -> Template UNIFORME (valeur: {template_np.mean():.1f})")
            else:
                print(f"  -> Template VARIÉ")

def compare_with_cell():
    """Compare unrevealed template avec une cellule uniforme"""
    print("\n" + "=" * 50)
    print("COMPARAISON UNREVEALED vs CELLULE")
    print("=" * 50)
    
    # Charger le template unrevealed
    unrevealed_path = os.path.join(TEMPLATES_DIR, 'inactive.png')
    unrevealed_pil = Image.open(unrevealed_path).convert('L')
    unrevealed_np = np.array(unrevealed_pil, dtype=np.float32)
    
    print(f"Template unrevealed:")
    print(f"  Moyenne: {unrevealed_np.mean():.1f}")
    print(f"  Écart-type: {unrevealed_np.std():.3f}")
    
    # Créer une cellule uniforme comme dans le screenshot
    cell_uniform = np.full((24, 24), 239.0, dtype=np.float32)
    
    print(f"\nCellule uniforme (screenshot):")
    print(f"  Moyenne: {cell_uniform.mean():.1f}")
    print(f"  Écart-type: {cell_uniform.std():.3f}")
    
    # Calculer la différence simple
    diff = np.abs(unrevealed_np - cell_uniform)
    print(f"\nDifférence moyenne: {diff.mean():.1f}")
    print(f"Différence max: {diff.max():.1f}")
    
    # Si la différence est faible, c'est un match
    if diff.mean() < 5.0:
        print("-> MATCH POTENTIEL (différence < 5)")
    else:
        print("-> PAS DE MATCH (différence trop élevée)")

def test_simple_matching():
    """Test un matching plus simple"""
    print("\n" + "=" * 50)
    print("TEST MATCHING SIMPLE")
    print("=" * 50)
    
    # Templates
    templates = {}
    for filename in os.listdir(TEMPLATES_DIR):
        if filename.endswith('.png'):
            template_path = os.path.join(TEMPLATES_DIR, filename)
            template_pil = Image.open(template_path).convert('L')
            template_np = np.array(template_pil, dtype=np.float32)
            
            # Mapping simple
            symbol_name = filename.replace('.png', '').lower()
            if 'flag' in symbol_name:
                symbol_name = 'flag'
            elif 'inactive' in symbol_name:
                symbol_name = 'unrevealed'
            elif 'vide' in symbol_name:
                symbol_name = 'empty'
            elif symbol_name.isdigit():
                symbol_name = f'number_{symbol_name}'
            
            templates[symbol_name] = template_np
    
    # Cellule test (uniforme comme dans les screenshots)
    test_cell = np.full((24, 24), 239.0, dtype=np.float32)
    
    print(f"Cellule test: valeur uniforme 239.0")
    
    # Tester chaque template avec une méthode simple
    best_match = None
    best_score = float('inf')
    
    for symbol_name, template in templates.items():
        # Méthode simple: différence moyenne
        diff = np.abs(template - test_cell)
        avg_diff = diff.mean()
        
        print(f"{symbol_name}: diff={avg_diff:.1f}")
        
        if avg_diff < best_score:
            best_score = avg_diff
            best_match = symbol_name
    
    print(f"\nMeilleur match: {best_match} (diff={best_score:.1f})")
    
    # Seuil pour match
    if best_score < 10.0:
        print("-> ACCEPTÉ comme match")
    else:
        print("-> REFUSÉ (différence trop élevée)")

if __name__ == "__main__":
    analyze_templates()
    compare_with_cell()
    test_simple_matching()
