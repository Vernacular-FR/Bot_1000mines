---
description: Spécification technique de la couche s4_solver (Grid Analyzer + Pattern Solver + CSP Solver)
---

# S04 SOLVER – Spécification technique

Le solver transforme la frontière issue de s3_storage en actions sûres (clics/drapeaux) en trois étapes successives :

1. **s40_grid_analyzer** – prépare un snapshot exploitable (statuts + vues).
2. **s41_propagator_solver** – applique les motifs déterministes (optionnel/futur dans le pipeline principal).
3. **s42_csp_solver** – segmente la frontière et effectue la résolution exacte locale (CSP).

## 1. Architecture

### 1.1 Vue d'ensemble
Vision (s2) ─▶ Storage (s3) ─▶ s40 Grid Analyzer ─▶ s41 Pattern Solver ─▶ s42 CSP Solver ─▶ Actions (s5/s6)

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
  - `s422_segmentation.py` : partition de la frontière en zones/composantes.
  - `s424_csp_solver.py` : backtracking exact (≤15 variables) + calcul de probabilités pondérées (best guess sinon).
  - `s421_frontiere_reducer.py` : réduction déterministe avant segmentation/CSP.
  - `s423_range_filter.py` : filtrage des composantes par taille (`max_component_size=500`).

### 1.3 Façade & orchestrateurs
- `controller.py` : récupère `FrontierSlice` + `cells` via StorageController, instancie `OptimizedSolver`, renvoie `SolverAction`.
- `s49_optimized_solver.py` : orchestrateur CSP-only (CspManager + reducer + segmentation + CSP + probabilités).
- `facade.py` : définit `SolverAction`, `SolverStats`, `SolverApi`.

## 2. Flux de données

### 2.1 Cycle typique
1. **Storage** fournit :
   - `cells` (bounds)
   - `active_set`
   - `frontier_set`
   - `ZoneDB` (index dérivé par `zone_id` + contraintes) et, en pratique, une vue dérivée `frontier_to_process` = union des cellules FRONTIER dont `FrontierRelevance == TO_PROCESS` (homogène par zone)
2. **s40 Grid Analyzer** (si utilisé) reclasse les `GridCell` (JUST_REVEALED→ACTIVE/FRONTIER/SOLVED) et construit `SolverFrontierView`.
3. **OptimizedSolver** choisit la phase :
   - boucle click-based sur ACTIVE (mode “dumb”)
   - ou CSP sur la frontière marquée `TO_PROCESS`
4. **ConstraintReducer** (s42) détecte immédiatement les safe/flag via contraintes locales.
5. **Segmentation + CSP** (s42) résolvent les composantes restantes.
   - Les **zones** sont persistées côté storage.
   - Les **components** sont éphémères (reconstruits au moment de la résolution).
6. **Controller** publie :
   - les décisions solver (SAFE/FLAG/GUESS) sous forme d’actions
   - un `StorageUpsert` qui met à jour :
     - `cells` (metadata solver)
     - `active_add/remove`, `frontier_add/remove`
     - `zone_upsert/zone_remove`

### 2.2 StorageUpsert émis par le solver
```python
StorageUpsert(
    cells={coord: GridCell(..., solver_status=SolverStatus.SOLVED, action_status=ActionStatus.SAFE)},
    active_add={...}, active_remove={...},
    frontier_add={...}, frontier_remove={...}
)
```

Note : la mise à jour ZoneDB est batchée dans le même `StorageUpsert` (zones upsert/remove).

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

### 3.4 `OptimizedSolver` API
- `solve()` : exécute reducer → segmentation/CSP.
- `get_safe_cells()`, `get_flag_cells()` : agrègent reducer + CSP.
- `get_best_guess()` : première cellule avec probabilité minimale > 0 (si aucune action sûre).

## 5. Règles & invariants

1. **Lecture seule storage** : s4 lit `active_set`, `frontier_set`, `cells` mais ne modifie pas directement les sets. Les modifications passent via `StorageUpsert`.

2. **Classifier unique** : toute logique JUST_REVEALED→ACTIVE/FRONTIER/SOLVED doit résider dans `grid_classifier`. Les scripts/tests doivent l’utiliser (pas de duplication).

3. **Motifs avant CSP** : PatternEngine tourne tant que des actions sont trouvées pour maximiser le coverage sans coût exponentiel.

4. **CSP borné** : backtracking autorisé jusqu’à 15 variables par composante (`LIMIT_ENUM`), sinon fallback probabiliste.

5. **Probabilités pondérées** : `zone_probabilities` = espérance (poids combinatoires). `best_guess` doit toujours refléter la probabilité la plus faible (>0).

6. **Threading contrôlé** (`02_run_solver_on_screenshots.py`) : solver exécuté dans un thread avec timeout (15s) pour éviter les blocages lors des tests.

7. **ZoneDB comme vérité de traitement CSP** :
   - une zone `BLOCKED` ne repasse pas au CSP tant que sa signature / son contenu ne change pas
   - toute zone impactée par une mise à jour (changement de `zone_id`, changement de contraintes) repasse `TO_PROCESS`

## 6. Performances cibles

- **Pattern Engine** : <5 ms par frontière (lookup O(1)).

- **CSP** : <50 ms pour composantes ≤15 variables ; fallback probabiliste si plus large.

- **Classifier** : O(n) sur les cellules du batch, n ≪ grille complète (juste zone visible).

- **Overlays runtime** : générés par `GameSolverServiceV2.solve_from_analysis_to_solver` avec chemins explicites `temp/games/{id}/s4_solver/` :
  - `s40_states_overlays` (zones pré-CSP via `FrontierClassifier`)
  - `s42_segmentation_overlay` (segmentation CSP)
  - `s43_csp_combined_overlay` (zones mises à jour + actions reducer/CSP opaques, guesses croix blanche)
  - Les dossiers sont fournis par `SessionStorage.build_game_paths`, évitant toute collision.

## 7. Documentation liée

- `PLAN_S4_SOLVER.md` : feuille de route détaillée.
- `doc/PIPELINE.md` : décrit la position de s4 dans la chaîne s0→s6.
- `development/PLAN_SIMPLIFICATION radicale.md` & `development/SYNTHESE_pipeline_refonte.md` : décisions historiques et plan d’exécution.
- `doc/META/CHANGELOG.md` : entrée « Solver – 2025-12-13 » documentant cette refonte.

---

*s4_solver reste stateless : il consomme un snapshot storage, produit un StorageUpsert + ActionBatch, puis attend la prochaine capture Vision. La mémoire inter-itérations (zones CSP + relevance) vit dans s3 via ZoneDB.*

---

## Annexe A – Pipeline “propagator” legacy (non implémenté dans la version actuelle)

Cette annexe conserve la description du plan historique (propagator + CSP hybride) issu de l’ancien `PLAN_S4_SOLVER.md`. Elle n’est pas implémentée dans la version actuelle (OptimizedSolver CSP-only), mais sert de référence si l’on souhaite réintroduire un moteur de motifs avancé.

### Étapes prévues (legacy)
- **Étape 0 – Grid Analyzer (s40)** : `grid_classifier` applique JUST_REVEALED→ACTIVE/FRONTIER/SOLVED, `grid_extractor` construit `SolverFrontierView` pour les solveurs.
- **Phase 1 – Frontière Reducer** (`s411_frontiere_reducer.py`) : règles locales (effective_value=0 ⇒ SAFE, effective_value = nb_fermées ⇒ FLAG), boucle jusqu’à stabilisation, overlays propagator.
- **Phase 2 – Subset Constraint Propagator** (`s412_subset_constraint_propagator.py`) : inclusion stricte C1⊆C2, déductions SAFE/FLAG sur les différences, boucle jusqu’à stabilité.
- **Phase 3 – Advanced Constraint Engine** (`s413_advanced_constraint_engine.py`) : pairwise elimination, inclusion partielle bornée, génération d’actions supplémentaires avant CSP.
- **Pipeline Propagator** (`s410_propagator_pipeline.py`) : enchaîne Phases 1→3 + “refresh” itératif pour absorber les triviales débloquées.
- **Second pass CSP** (`csp_manager.py` + `s423_*`) : segmentation, stabilité, CSP exact sur composantes stables ≤ LIMIT_ENUM, probabilités par zone.

### Intégration souhaitée (legacy)
- Séquence : propagate (phases 1→3) tant qu’il y a du progrès, puis CSP uniquement sur composantes stables/taille bornée.
- Sorties attendues : `safe_cells`, `flag_cells`, `progress_cells` + metadata (probabilités zone), overlays de segmentation/propagator.
- Invariants visés : classification centralisée dans `grid_classifier`; propagation déterministe avant CSP pour limiter le coût exponentiel.

### Statut
- Non implémenté dans la branche actuelle (remplacé par `OptimizedSolver` CSP-only). Gardé ici comme piste d’évolution si un moteur de motifs avancé doit être réintroduit.