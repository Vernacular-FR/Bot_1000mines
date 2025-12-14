---
description: Spécification technique de la couche s4_solver (Grid Analyzer + Pattern Solver + CSP Solver)
---

# S04 SOLVER – Spécification technique

Le solver transforme la frontière issue de s3_storage en actions sûres (clics/drapeaux) en trois étapes successives :

1. **s40_grid_analyzer** – prépare un snapshot exploitable (statuts + vues).
2. **s41_propagator_solver** – applique les motifs déterministes (First Pass) avec une passe itérative de clôture.
3. **s42_csp_solver** – segmente la frontière et effectue la résolution exacte locale (Second Pass).

## 1. Architecture

### 1.1 Vue d'ensemble
Vision (s2) ─▶ Storage (s3) ─▶ s40 Grid Analyzer ─▶ s41 Pattern Solver ─▶ s42 CSP Solver ─▶ Actions (s5/s6)
                   ↑               (statuts + vues)     (motifs O(1))          (CSP exact)        (flags/open)
                   └────────────── StorageUpsert (frontier_add/remove, unresolved_remove)

### 1.2 Sous-modules
- **s40_grid_analyzer/**
  - `grid_classifier.py` : applique les transitions JUST_REVEALED → ACTIVE/FRONTIER/SOLVED en mémoire (sans relecture complète de storage).
  - `grid_extractor.py` : expose `SolverFrontierView`, implémentant `FrontierViewProtocol` (segmentation) et `GridAnalyzerProtocol` (CSP).
  - Re-exporte les types essentiels (`Segmentation`, `CSPSolver`, `SolverFrontierView`) pour compatibilité ascendante.
- **s41_propagator_solver/**
  - `pattern_engine.py` : moteur de motifs 3×3/5×5, lookup base 16, propagation tant que des actions sont trouvées.
  - `s410_propagator_pipeline.py` : chaîne "Iterative → Subset → Advanced → Iterative refresh". La reprise finale d’Iterative s’assure d’absorber les cellules triviales débloquées par la phase 3 (cas typique : pairwise révèle toutes les mines sauf une cellule encore marquée FRONTIER).
  - Consomme `self.cells` + flags déterminés par s40 (just revealed, inferred flags).
- **s42_csp_solver/**
  - `s420_segmentation.py` : partition de la frontière en zones/composantes.
  - `csp_solver.py` : backtracking exact (≤15 variables) + calcul de probabilités pondérées (best guess sinon).
  - `frontier_reducer.py` : réduction déterministe (unit constraints) avant motifs/CSP.

### 1.3 Façade & orchestrateurs
- `controller.py` : récupère `FrontierSlice` + `cells` via StorageController, instancie `HybridSolver`, renvoie `SolverAction`.
- `s43_hybrid_solver.py` : orchestre ConstraintReducer → PatternEngine → Segmentation/CSP → probabilités → actions.
- `facade.py` : définit `SolverAction`, `SolverStats`, `SolverApi`.

## 2. Flux de données

### 2.1 Cycle typique
1. **Storage** fournit `frontier_slice`, `cells` (bounds) et `unresolved_set`.
2. **s40 Grid Analyzer** reclasse les `GridCell` (JUST_REVEALED→ACTIVE/FRONTIER/SOLVED) et construit `SolverFrontierView`.
3. **ConstraintReducer** (s42) détecte immédiatement les safe/flag via contraintes locales.
4. **PatternEngine** (s41) applique les motifs sur les cellules TO_PROCESS (Active/Frontier) et relance Iterative après la phase Advanced pour absorber les cellules révélées indirectement.
5. **Segmentation + CSP** (s42) résolvent les composantes restantes, calculent les probabilités de mines par zone.
6. **HybridSolver** agrège constraint_safe + pattern_safe + csp_safe, produit également:
   - `pattern_flag_cells`, `constraint_flag_cells`, `csp` flags.
   - `zone_probabilities` pour best guess si aucune action sûre.
7. **Controller** convertit ces résultats en `SolverAction` (CLICK/FLAG/GUESS) et met à jour storage via `StorageUpsert` (`frontier_add/remove`, `unresolved_remove`, `cells` à jour pour solver_status/action_status).

### 2.2 StorageUpsert émis par le solver
```python
StorageUpsert(
    cells={coord: GridCell(..., solver_status=SolverStatus.SOLVED, action_status=ActionStatus.SAFE)},
    unresolved_remove={...},          # cellules traitées
    frontier_add={...}, frontier_remove={...}  # propagation analytique
)
```

## 3. Interfaces clés

### 3.1 `SolverFrontierView`
Implémente :
- `get_frontier_cells()` → Set des cellules fermées à traiter.
- `get_constraints_for_cell(x, y)` → Liste des coordonnées ouvertes numérotées adjacentes.
- `get_cell(x, y)` → Valeur num/FLAG/UNKNOWN selon `GridCell` (utilisé par CSP).

### 3.2 `PatternEngine.solve_patterns()`
Retourne `PatternResult` :
- `safe_cells`, `flag_cells`, `reasoning`.
- Consomme `cells` (dict) et `inferred_flags`.
- Exécutée tant que `safe_cells` ou `flag_cells` non vide.

### 3.3 `CSPSolver.solve_component(component)`
- `component` = ensemble de zones + contraintes issues de `Segmentation`.
- Retourne une liste de `Solution(zone_assignment)` ; chaque solution mappe zone → nb_mines.
- `get_prob_weight(zones)` calcule le poids combinatoire pour pondérer les probabilités.

### 3.4 `HybridSolver` API
- `solve()` : exécute ConstraintReducer → PatternEngine → Segmentation/CSP.
- `get_safe_cells()`, `get_flag_cells()` : agrègent constraint + pattern + CSP.
- `get_best_guess()` : première cellule avec probabilité minimale > 0 (si aucune action sûre).

## 4. Tests & outils debug

- `test_unitaire/00_run_zone_overlay.py` : Vision → Grid Analyzer → Overlay ACTIVE/FRONTIER/SOLVED. Vérifie que la classification est centralisée dans `FrontierClassifier`.
- `test_unitaire/02_run_solver_on_screenshots.py` : pipeline complet (vision → storage → solver) sur screenshots locaux. Produit overlays (segmentation/pattern/CSP) et logs motif/CSP.
- Dossier `test_unitaire/vision_overlays`, `s40_zones_overllays`, `solver_overlays` : résultats visuels pour audit rapide.

## 5. Règles & invariants

1. **Lecture seule storage** : s4 lit `frontier_set`, `unresolved_set`, `cells` mais ne modifie pas directement les sets. Les modifications passent via `StorageUpsert`.
2. **Classifier unique** : toute logique JUST_REVEALED→ACTIVE/FRONTIER/SOLVED doit résider dans `grid_classifier`. Les scripts/tests doivent l’utiliser (pas de duplication).
3. **Motifs avant CSP** : PatternEngine tourne tant que des actions sont trouvées pour maximiser le coverage sans coût exponentiel.
4. **CSP borné** : backtracking autorisé jusqu’à 15 variables par composante (`LIMIT_ENUM`), sinon fallback probabiliste.
5. **Probabilités pondérées** : `zone_probabilities` = espérance (poids combinatoires). `best_guess` doit toujours refléter la probabilité la plus faible (>0).
6. **Threading contrôlé** (`02_run_solver_on_screenshots.py`) : solver exécuté dans un thread avec timeout (15s) pour éviter les blocages lors des tests.

## 6. Performances cibles

- **Pattern Engine** : <5 ms par frontière (lookup O(1)).
- **CSP** : <50 ms pour composantes ≤15 variables ; fallback probabiliste si plus large.
- **Classifier** : O(n) sur les cellules du batch, n ≪ grille complète (juste zone visible).
- **Overlays debug** : facultatifs en production, mais doivent rester disponibles en test unitaire (`--overlay`).

## 7. Documentation liée

- `PLAN_S4_SOLVER.md` : feuille de route détaillée.
- `doc/PIPELINE.md` : décrit la position de s4 dans la chaîne s0→s6.
- `development/PLAN_SIMPLIFICATION radicale.md` & `development/SYNTHESE_pipeline_refonte.md` : décisions historiques et plan d’exécution.
- `doc/META/CHANGELOG.md` : entrée « Solver – 2025-12-13 » documentant cette refonte.

---

*s4_solver reste strictement stateless entre deux résolutions : il consomme un snapshot storage, produit un StorageUpsert + ActionBatch, puis attend la prochaine capture Vision.* 