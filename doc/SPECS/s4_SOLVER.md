---
description: Spécification technique de la couche s4_solver (Grid Analyzer + Pattern Solver + CSP Solver)
---

# S04 SOLVER – Spécification technique

Le solver transforme un snapshot issu de s3_storage en actions (`SAFE/FLAG/GUESS`) via un pipeline en 3 temps :

1. **s4a_status_analyzer** (post-vision) : reclassement topologique `JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED/MINE` et overlays de statut.
2. **s4b_csp_solver** : réduction déterministe + CSP/segmentation si nécessaire (décisions `SAFE/FLAG/GUESS`).
3. **s4d_post_solver_sweep** : actions bonus de “sweep” (clics `SAFE`) sur les voisines `ACTIVE` des cellules `TO_VISUALIZE`.

## 1. Architecture

### 1.1 Vue d'ensemble
Vision (s2) ─▶ Storage (s3) ─▶ s4a_status_analyzer (classification + focus) ─▶ s4b_csp_solver (reducer+CSP) ─▶ s4d_post_solver_sweep (bonus) ─▶ Actions (s5/s6)

### 1.2 Sous-modules
- **s4a_status_analyzer/**
  - `status_analyzer.py` : classification topologique (reclustering) et génération de l’overlay status.
  - `focus_actualizer.py` : promotion des focus levels autour des cellules qui viennent de changer de statut.
  - `action_mapper.py` : mapping des actions solver vers des mises à jour storage (et rétrogradations REDUCED/PROCESSED).
- **s4b_csp_solver/**
  - `csp_manager.py` : orchestre reducer + segmentation + CSP.
  - `reducer.py` : propagation contrainte déterministe (safe/flag) sur actives.
  - `segmentation.py` : segmentation de la frontière en zones/composantes.
- **s4c_overlays/**
  - `overlay_status.py` : rendu des zones par statut.
  - `overlay_combined.py` : rendu zones + actions (symboles blancs sans fond).
- **s4d_post_solver_sweep/**
  - `sweep_builder.py` : génération d’actions `SAFE` bonus ciblées.

> Alerte (hors champ de vision) : si la capture ne couvre pas toutes les voisines UNREVEALED d’une ACTIVE, la frontière est incomplète. Seule la vision peut injecter ces UNREVEALED en storage. Recentrer/capturer à nouveau pour compléter la frontière.

- **s41_propagator_solver/**
  - `pattern_engine.py` : moteur de motifs 3×3/5×5, lookup base 16, propagation tant que des actions sont trouvées.
  - `s410_propagator_pipeline.py` : chaîne "Iterative → Subset → Advanced → Iterative refresh". La reprise finale d’Iterative s’assure d’absorber les cellules triviales débloquées par la phase 3 (cas typique : pairwise révèle toutes les mines sauf une cellule encore marquée FRONTIER).

### 1.3 Façade & orchestrateurs
- `controller.py` : récupère `FrontierSlice` + `cells` via StorageController, instancie `OptimizedSolver`, renvoie `SolverAction`.
- `s49_optimized_solver.py` : orchestrateur (CspManager + reducer + segmentation + CSP + probabilités), avec CSP optionnel selon la stratégie de bypass.
- `facade.py` : définit `SolverAction`, `SolverStats`, `SolverApi`.

## 2. Flux de données

### 2.1 Cycle typique (séquentiel, sans parallélisation)
1. **Vision → Storage** : `storage.update_from_vision()` écrit les cellules en `JUST_VISUALIZED` avec `raw_state` et `logical_state`.
2. **Pipeline 1 (post-vision)** : `StatusManager.pipeline_post_vision()`
   - `StatusAnalyzer.analyze()` : reclasse `JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED/MINE` (selon `logical_state` et voisinage).
   - `FocusActualizer.promote_focus()` : réveille les voisines des cellules qui viennent de changer (focus `TO_REDUCE/TO_PROCESS`).
3. **Pipeline solver** : `CspManager.run()` produit des ensembles `safe_cells/flag_cells` + éventuellement `best_guess`.
4. **Pipeline 2 (post-solver)** : `ActionMapper.map_actions()`
   - `FLAG` → `logical_state=CONFIRMED_MINE`, `solver_status=MINE`
   - `SAFE/GUESS` → `solver_status=TO_VISUALIZE` (le `logical_state` reste `UNREVEALED` tant que la vision n’a pas relu)
   - rétrograde les anciennes `ACTIVE/FRONTIER` non résolues en `REDUCED/PROCESSED`.
5. **Sweep bonus** : `build_sweep_actions()` génère des `SAFE` uniquement pour les voisines `ACTIVE` des cellules `TO_VISUALIZE`.

Justification (stratégie actuelle) :

- **Deux modes solver** :
  - mode 1 = **réduction de frontière** (toujours) : règles locales de contrainte (saturation / égalité) très rapides, nécessaires de toute façon avant CSP.
  - mode 2 = **CSP** (optionnel) : appelé uniquement si la réduction n’apporte pas assez d’actions.
- Le solver publie seulement SAFE/FLAG/GUESS (GUESS off par défaut). Pas de priorité “SAFE-first” hors de la logique de réduction : dès qu’une case est déduite SAFE, elle passe en `TO_VISUALIZE` (plus `FRONTIER`) et sera cliquée par l’exécuteur.

- **Heuristiques d’exécution hors solver** : le solver ne produit que des `SolverAction` (SAFE/FLAG/GUESS) ; toute astuce d’exécution (ex: double-clic SAFE, clics opportunistes sur des actives voisines) vit dans s5.

### 2.2 StorageUpsert émis par le solver (actions solver uniquement)

```python
StorageUpsert(
    cells={coord: GridCell(..., solver_status=SolverStatus.TO_VISUALIZE)},
    active_add={...}, active_remove={...},
    frontier_add={...}, frontier_remove={...},
    to_visualize={...},
)
```

## 4. Runtime interne (SolverRuntime) – snapshot mutable + dirty flags

- Le solver utilise un **SolverRuntime** interne (snapshot mutable + dirty flags) au lieu de chaîner des `get_snapshot()`/`apply_upsert()` sur le storage.
- Pipeline exécuté **sur un seul état partagé** :
  1. **Post-vision** : `StatusManager.pipeline_post_vision()` produit un `StorageUpsert` appliqué immédiatement au runtime.
  2. **CSP** : le reducer/CSP consomme le snapshot courant, produit un upsert appliqué au runtime.
  3. **Post-solver** : `ActionMapper` produit un upsert (FLAG → MINE, SAFE/GUESS → TO_VISUALIZE, rétrogradations) appliqué au runtime.
  4. **Sweep** : lit le snapshot final, génère des actions SAFE bonus (ne mute pas le runtime).
- **Dirty flags** : chaque cellule modifiée est marquée dirty lors de l’application d’un upsert. À la fin du pipeline, un upsert unique est émis vers le storage (cellules dirty uniquement). Le storage réel n’est mis à jour qu’une seule fois.
- **Overlays** : calculés à partir du snapshot final du runtime (post-sweep) sans resnapshot intermédiaire.

### 4.1 Correctifs récents (focus, overlays, CSP)
- **Classification** : `StatusAnalyzer` ne reclasse plus que les `JUST_VISUALIZED`; les cellules FRONTIER/ACTIVE existantes conservent leurs focus levels.
- **Persistance focus** : `storage.update_from_vision` préserve `focus_level_active` et `focus_level_frontier` des cellules inchangées; plus de perte de `REDUCED/PROCESSED` entre deux itérations.
- **Overlay fidélité** : `overlay_combined` n’applique plus de transitions manuelles ; les overlays reflètent strictement l’état du snapshot (runtime).
- **CSP borné** : limite configurable `CSP_CONFIG['max_zones_per_component']=50` (config.py) pour éviter l’explosion du backtracking sur les grandes frontières.

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

2. **Classifier unique** : toute logique `JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED/MINE` doit résider dans `StatusAnalyzer` (pas de duplication).

3. **Motifs avant CSP** : PatternEngine tourne tant que des actions sont trouvées pour maximiser le coverage sans coût exponentiel.

4. **CSP borné** : backtracking autorisé jusqu’à 15 variables par composante (`LIMIT_ENUM`), sinon fallback probabiliste.

5. **Probabilités pondérées** : `zone_probabilities` = espérance (poids combinatoires). `best_guess` doit toujours refléter la probabilité la plus faible (>0).

6. **Threading contrôlé** (`02_run_solver_on_screenshots.py`) : solver exécuté dans un thread avec timeout (15s) pour éviter les blocages lors des tests.

7. **ZoneDB comme vérité de traitement CSP** :
   - une zone `PROCESSED` est considérée implicitement comme bloquée 
   - toute zone impactée par une mise à jour (changement de `zone_id`, changement de contraintes) repasse `TO_PROCESS`

8. **Relevance déterministe (FocusLevel)** :
   - si une cellule devient **ACTIVE** (SolverStatus) ou si son voisinage change, alors `ActiveRelevance = TO_REDUCE`
   - si une cellule devient **FRONTIER** (SolverStatus) ou si sa zone/contraintes change, alors `FrontierRelevance = TO_PROCESS` (propagé à toute la zone)
   - une cellule ACTIVE passe `REDUCED` quand la réduction ne produit plus rien dans l’état courant (et peut repasser `TO_REDUCE` si un voisin devient ACTIVE/SOLVED)
   - une cellule FRONTIERE passe `PROCESSED` une fois la zone traitée par le csp (et peut repasser `TO_PROCESS` si un voisin devient ACTIVE/SOLVED ; option envisagée : réactiver toute la zone associée)
   - **Repromotion des focus levels (centralisée dans s45_focus_refresher / focus_actualizer)**

La repromotion des focus levels est déclenchée par les changements topologiques vers :
- `TO_VISUALIZE` (safe à cliquer)
- `SOLVED` (case opennumber décor et vide)  
- `MINE` (mine confirmée)  
- `ACTIVE` (nouvelle information)

**Deux points de repromotion dans le pipeline :**

1. **Post-vision** : Après le reclustering des états dans `s40_states_analyzer/states_recluster.py`
   - Gère les changements topologiques issus de la vision (JUST_VISUALIZED → ACTIVE/SOLVED/MINE/FRONTIER)
   - Repromotion des voisines ACTIVES et zones FRONTIER impactées
   - `segmentation=None` (pas de zones disponibles à ce stade)

2. **Post-solver** : Après les actions solver (safe/flag) dans `s49_optimized_solver.py`
   - Gère les changements topologiques issus des résolutions (TO_VISUALIZE/SOLVED/MINE)
   - Repromotion avec `segmentation` disponible pour les zones FRONTIERes

   - **cohérence stricte** : `focus_level_active` n’est autorisé que si `solver_status == ACTIVE`; `focus_level_frontier` n’est autorisé que si `solver_status == FRONTIER`; tous les autres états exigent les deux focus à `None` (enforcé par s3 storage).

9. **Actions publiées** :
   - `actions` = SAFE/FLAG/GUESS.
   - `sweep_actions` = clics bonus `SAFE` sur les voisines `ACTIVE` des cellules `TO_VISUALIZE`.

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
- **Étape 0 – Grid Analyzer (s40)** : `grid_classifier` applique JUST_VISUALIZED→ACTIVE/FRONTIER/SOLVED, `grid_extractor` construit `SolverFrontierView` pour les solveurs.
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