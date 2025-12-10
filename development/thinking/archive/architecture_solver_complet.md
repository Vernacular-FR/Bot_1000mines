# 🧩 Architecture Complète du Solver Minesweeper

> **Objectif pédagogique** : Comprendre étape par étape comment un screenshot devient une solution visuelle.

## 🎯 Vue d'Ensemble - Le Pipeline Complet

### Le Problème
**Entrée** : Un screenshot du jeu Minesweeper
**Sortie** : Le même screenshot avec des indications visuelles des cases sûres et des mines

### Le Flux Principal (3 Étapes)
```
📸 Screenshot ──➤ 🤖 Analyse ──➤ 💾 Base de Données ──➤ 🧠 Résolution ──➤ 🎨 Overlay
```

### Détail des Étapes
1. **📸 STAGE 1** : Extraire les données du screenshot (Vision)
2. **🧠 STAGE 2** : Résoudre mathématiquement (CSP + Probabilités)
3. **🎨 STAGE 3** : Générer l'overlay visuel (Affichage)

---

## 🏗️ Architecture Modulaire - Les 7 Couches

### 📁 Structure des Fichiers (Arborescence)
```
lib/solver/
├── 📊 database/
│   ├── cell_analyzer.py         # 🔍 Analyse d'image
│   └── grid_db.py               # 💾 Base de données JSON
├── 🎯 solver/
│   ├── core/
│   │   ├── grid_state.py        # 📋 Extraction données brutes
│   │   ├── frontier.py          # 🎯 Calcul frontière
│   │   ├── grid_analyzer.py     # 🎼 Orchestration
│   │   ├── segmentation.py      # 🗂️  Zonage
│   ├── csp/
│   │   └── solver.py        # 🧮 Résolution contraintes
│   ├── hybrid_solver.py         # 🎯 Orchestrateur principal
│   └── visualization/
│       └── segmentation_visualizer.py  # 🎨 Visualisation
└── visualization/
    └── solver_overlay_generator.py     # 🎨 Overlay final
```

---

## 🎨 COUCHE 1 : Vision - Analyse d'Image

### 🎯 Rôle
Transformer une image en données utilisables par le solver.

### 📊 Schéma de Flux
```
Screenshot PNG ──➤ 📖 Templates ──➤ 🔍 Template Matching ──➤ 📋 Liste Cellules
                      (1-8,flag,   ──➤ 🏷️  Classification ──➤ 📍 Coordonnées
                       empty)                      (x,y,type)
```

### 🔧 Code Exemple (Simplifié)
```python
# 1. Initialisation
analyzer = CellAnalyzer()
templates = analyzer.load_templates("assets/symbols/")

# 2. Analyse
cells = analyzer.analyze_screenshot("screenshot.png")

# Résultat : Liste de dictionnaires
cells = [
    {"x": 0, "y": 0, "type": "number_1", "confidence": 0.95},
    {"x": 1, "y": 0, "type": "empty", "confidence": 0.98},
    {"x": 0, "y": 1, "type": "unrevealed", "confidence": 0.92}
]
```

### 📈 Métriques
- **Temps** : ~0.3s pour 1800 cellules
- **Précision** : >95% avec templates optimisés

---

## 💾 COUCHE 2 : Persistance - Base de Données

### 🎯 Rôle
Stocker et gérer l'état de la grille pendant tout le processus.

### 📊 Structure JSON
```json
{
  "cells": [
    {
      "x": 0, "y": 0,
      "type": "number_1",
      "confidence": 0.95,
      "state": "TO_PROCESS"
    }
  ],
  "actions": [
    {
      "id": 1,
      "type": "SAFE",
      "x": 1, "y": 1,
      "executed": false
    }
  ],
  "summary": {
    "total_cells": 1800,
    "known_cells": 67,
    "bounds": [-30, -15, 29, 14]
  }
}
```

### 🔧 Interface Principale
```python
db = GridDB("temp/grid_state_db.json")

# Ajouter des cellules
db.add_cell(x, y, {"type": "number_1", "confidence": 0.9})

# Récupérer des données
bounds = db.get_bounds()  # [-30, -15, 29, 14]
cells = db.get_cells()    # Toutes les cellules
```

---

## 🧠 COUCHE 3 : Solver - Architecture Refactorisée

### 🎯 Le Refactoring (Pourquoi ?)

**Avant** (Monolithique) :
```
Grid (énorme classe)
├── Données brutes (GridDB)
├── Calcul frontière
├── Segmentation
└── Résolution CSP
❌ Tout mélangé, difficile à tester
```

**Après** (Modulaire) :
```
GridAnalyzer (orchestrateur)
├── GridState (données)
├── Frontier (frontière)
├── Segmentation (zonage)
└── CSPSolver (résolution)
✅ Chaque partie indépendante
```

### 3.1 📋 GridState - Extraction Données
```python
class GridState:
    def __init__(self, db: GridDB):
        self.cells = {}  # (x,y) -> valeur numérique
        self.width = ...
        self.height = ...
        self._load_from_db(db)

    def get_cell(self, x, y) -> int:
        """Retourne UNKNOWN, FLAG, ou 0-8"""
        return self.cells.get((x, y), None)
```

**Rôle** : Interface propre vers les données brutes.

### 3.2 🎯 Frontier - Calcul Frontière
```python
class Frontier:
    def __init__(self, grid_state: GridState):
        self.cells = set()  # Cases inconnues adjacentes aux chiffres
        self.constraints = {}  # Case inconnue -> liste des chiffres voisins
        self._build()

    def _build(self):
        # Pour chaque chiffre (1-8)
        for (x, y), val in grid_state.cells.items():
            if 0 <= val <= 8:
                # Chercher voisins inconnus
                unknowns = self._get_unknown_neighbors(x, y)
                for ux, uy in unknowns:
                    self.cells.add((ux, uy))
                    # Cette case inconnue est contrainte par ce chiffre
                    self.constraints[(ux, uy)].append((x, y))
```

**Rôle** : Identifier les cases "jouables" et leurs contraintes.

### 3.3 🎼 GridAnalyzer - Orchestration
```python
class GridAnalyzer:
    def __init__(self, db: GridDB):
        self.grid_state = GridState(db)
        self.frontier = Frontier(self.grid_state)

    # Délégation transparente
    def get_cell(self, x, y): return self.grid_state.get_cell(x, y)
    def get_bounds(self): return self.grid_state.get_bounds()
```

**Rôle** : Point d'entrée unique pour tous les modules.

---

## 🗂️ COUCHE 4 : Segmentation - Création des Zones

### 🎯 Concept Clé : Zones vs Composants

**Zone** : Groupe de cases inconnues partageant les **mêmes contraintes**
```
Exemple concret :
Case A contrainte par chiffres (1,2) et (3,4)
Case B contrainte par chiffres (1,2) et (3,4)
➡️ Case A et B forment la même ZONE
```

**Composant** : Ensemble de zones interconnectées (à résoudre ensemble)
```
Zone 1 ── contrainte ── Zone 2  ➡️ Même composant
Zone 3 (isolée)                ➡️ Composant séparé
```

### 📊 Schéma de Segmentation
```
Frontière (46 cases inconnues)
├── Signature contraintes identiques
├── Groupement en zones
└── Connexité → composants

Résultat :
├── Composant A : 3 zones, 4 contraintes
├── Composant B : 1 zone, 2 contraintes
└── Composant C : 42 zones, 32 contraintes
```

### 🔧 Code Exemple
```python
segmentation = Segmentation(grid_analyzer)

print(f"Zones: {len(segmentation.zones)}")
print(f"Composants: {len(segmentation.components)}")

for comp in segmentation.components:
    print(f"Composant {comp.id}: {len(comp.zones)} zones")
```

---

## 🧮 COUCHE 5 : CSP - Résolution par Contraintes

### 🎯 Rappel CSP (Constraint Satisfaction Problem)

**Variables** : Zones (à décider : 0 ou 1 mine)
**Domaines** : [0, 1] pour chaque zone
**Contraintes** : "Somme des mines = nombre indiqué"

### 📊 Exemple Concret
```
Zone A ──┐
Zone B ──┼───➤ Contrainte : Somme = 2
Zone C ──┘

Solutions possibles :
├── A=1, B=1, C=0 ✓
├── A=1, B=0, C=1 ✓
├── A=0, B=1, C=1 ✓
└── A=0, B=0, C=2 ✗ (impossible)
```

### 🔧 Algorithme Backtracking
```python
def solve_component(component):
    solutions = []

    def backtrack(assignment, unassigned, domains):
        if not unassigned:  # Plus de variables
            solutions.append(assignment.copy())
            return

        var = unassigned[0]  # Prendre première zone
        for value in domains[var]:  # Essayer 0 ou 1 mine
            if is_consistent(var, value):  # Vérifier contraintes
                assignment[var] = value
                backtrack(assignment, unassigned[1:], domains)
                del assignment[var]

    backtrack({}, component.zones, {z.id: [0,1] for z in component.zones})
    return solutions
```

---

## 🎯 COUCHE 6 : Orchestration - Solver Hybride

### 🎯 Rôle
Orchestrer tout le pipeline et calculer les probabilités.

### 📊 Flux de Résolution
```
Pour chaque composant :
├── 1. Résoudre CSP → Toutes les solutions valides
├── 2. Calculer poids de chaque solution
└── 3. Agréger probabilités par zone

Exemple :
Composant avec 3 solutions équiprobables :
├── Solution 1: Zone A=1, B=0 → Poids = C(5,1) × C(3,0) = 5
├── Solution 2: Zone A=0, B=1 → Poids = C(5,0) × C(3,1) = 3
└── Solution 3: Zone A=0, B=0 → Poids = C(5,0) × C(3,0) = 1

Probabilités :
├── Zone A: (5×1 + 3×0 + 1×0) / (5+3+1) = 33%
├── Zone B: (5×0 + 3×1 + 1×0) / (5+3+1) = 25%
```

### 🔧 Code Principal
```python
solver = HybridSolver(grid_analyzer)

# Résolution complète
solver.solve()

# Résultats
safe_cells = solver.get_safe_cells()    # Probabilité = 0%
flag_cells = solver.get_flag_cells()    # Probabilité = 100%

# Sauvegarde
solver.save_to_db(db)
```

---

## 🎨 COUCHE 7 : Visualisation - Overlays

### 🎯 Deux Types d'Overlays

#### 7.1 Segmentation Overlay (Debug)
**Objectif** : Vérifier que le zonage est correct
```
Image de base
├── Cases de la frontière (bleu)
├── Numéros de zones (Z1, Z2, etc.)
└── Contraintes (bordures rouges)
```

#### 7.2 Solution Overlay (Final)
**Objectif** : Montrer les actions à effectuer
```
Image de base
├── Cases sûres (cercle vert)
├── Mines certaines (drapeau rouge)
└── Actions numérotées (ordre suggéré)
```

### 📊 Schéma de Génération
```
Screenshot ──➤ Coordonnées grille ──➤ Position pixels ──➤ Dessin ──➤ Fusion ──➤ Sauvegarde
     ↓              ↓                        ↓           ↓          ↓           ↓
  Base RGBA      (x,y) → pixel            box coords   formes     alpha       PNG
```

---

## 🚀 Pipeline Complet d'Exécution

### 📋 Commande Principale
```bash
python development/test_pipeline_full.py
```

### 📊 Flux Détaillé
```
STAGE 1: Peuplement
├── CellAnalyzer.analyze_screenshot() → Liste cellules
├── GridDB.clear_all() → Base vide
├── GridDB.add_cell() → Peuplement
└── GridDB.flush_to_disk() → Sauvegarde

STAGE 1.5: Segmentation (Optionnel)
├── GridAnalyzer(db) → Architecture refactorisée
├── Segmentation(analyzer) → Zones + Composants
├── SegmentationVisualizer.visualize() → Overlay debug
└── Sauvegarde PNG

STAGE 2: Résolution
├── HybridSolver(analyzer) → Orchestrateur
├── solver.solve() → Résolution complète
├── solver.get_safe_cells() → Cases sûres
├── solver.get_flag_cells() → Mines certaines
└── solver.save_to_db() → Persistance résultats

STAGE 3: Overlay Final
├── SolverOverlayGenerator.generate_overlay()
├── Chargement screenshot
├── Dessin actions (verts/rouges)
└── Sauvegarde overlay final
```

### ⏱️ Temps d'Exécution Typiques
- **Stage 1** : 0.3s (analyse image)
- **Stage 1.5** : 0.01s (segmentation)
- **Stage 2** : 0.05s (résolution CSP)
- **Stage 3** : 0.1s (génération overlay)
- **Total** : ~0.5s

---

## 🎯 Points Clés à Retenir

### 1. **Séparation des Responsabilités**
Chaque couche fait UNE chose et la fait bien :
- Vision → Extraction données
- Persistance → Stockage
- Solver → Résolution mathématique
- Visualisation → Affichage

### 2. **Architecture Refactorisée**
L'ancien `Grid` monolithique est maintenant :
```
GridAnalyzer (chef d'orchestre)
├── GridState (données)
├── Frontier (logique métier)
├── Segmentation (optimisation)
└── CSP (résolution)
```

### 3. **Flux de Données**
Les données circulent de couche en couche :
```
Image → Cellules → DB → GridState → Frontier → Segmentation → CSP → Solutions → Overlay
```

### 4. **Indépendance des Composants**
Chaque composant CSP peut être résolu séparément :
- **Avantage** : Parallélisation possible
- **Optimisation** : Réduction espace de recherche

### 5. **Probabilités = Combinatoire**
```
P(mine) = Σ(solutions_avec_mine) × poids(solutions) / Σ(toutes_solutions × poids)
```

---

## 🔄 Évolutions Futures

### 🤖 Intégration Bot
1. **Interface clavier/souris** pour actions automatiques
2. **Boucle de jeu** : Screenshot → Résolution → Action → Répéter
3. **Gestion d'erreurs** : Retry en cas d'échec

### ⚡ Optimisations
1. **Cache templates** pour analyse plus rapide
2. **Parallélisation CSP** sur plusieurs cœurs
3. **Apprentissage** des patterns récurrents

### 📊 Analytics
1. **Statistiques** de performance par niveau
2. **Historique** des parties résolues
3. **Métriques** de précision et rapidité

---

## 🧪 Comment Tester

### Test Complet (avec segmentation overlay)
```bash
python development/test_pipeline_full.py
```

### Test Segmentation Seulement
```bash
python development/test_phase1_visualization.py
```

### Test Résolution Seulement
```bash
python development/test_phase2_solver.py
```

### Debug Étape par Étape
```python
# Dans un script Python
from lib.solver.database.cell_analyzer import CellAnalyzer
from lib.solver_new.core.grid_analyzer import GridAnalyzer
from lib.solver_new.hybrid_solver import HybridSolver

# Étape 1: Analyse
analyzer = CellAnalyzer()
cells = analyzer.analyze_screenshot("screenshot.png")

# Étape 2: Architecture
grid_analyzer = GridAnalyzer(db)
print(f"Frontière: {grid_analyzer.frontier.size()} cases")

# Étape 3: Résolution
solver = HybridSolver(grid_analyzer)
solver.solve()
print(f"Solutions trouvées: {len(solver.solutions_by_component)}")
```
