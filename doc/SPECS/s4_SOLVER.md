---
description: Spécification technique de la couche s4_solver (Grid Analyzer + Pattern Solver + CSP Solver)
---

# S04 SOLVER – Spécification technique

Le solver transforme la frontière issue de s3_storage en actions sûres (clics/drapeaux) en trois étapes successives :

1. **s40_grid_analyzer** – prépare un snapshot exploitable (statuts + vues).
2. **s41_propagator_solver** – applique les motifs déterministes (optionnel/futur dans le pipeline principal).
3. **s42_csp_solver** – applique une réduction de frontière déterministe, puis (si nécessaire) segmente la frontière et effectue la résolution exacte locale (CSP).

## 1. Architecture

### 1.1 Vue d'ensemble
Vision (s2) ─▶ Storage (s3) ─▶ s40 State Analyzer (reclustering JUST_VISUALIZED→ACTIVE/FRONTIER/SOLVED + repromotions voisines via **FocusActualizer**) ─▶ s42 frontiere_reducer (ACTIVE→REDUCED) + CSP Solver (FRONTIER→PROCESSED) ─▶ cleanup ─▶ Actions (s5/s6)

### 1.2 Sous-modules
- **s40_grid_analyzer/**
  - `state_analyzer.py` : applique les transitions JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED en mémoire (sans relecture complète de storage) et initialise les focus levels (TO_REDUCE/TO_PROCESS).
  - `grid_classifier.py` : classification topologique des cellules (ACTIVE/FRONTIER/SOLVED/UNREVEALED).
  - `frontier_view_factory.py` : construit SolverFrontierView depuis le snapshot storage.
- **s45_focus_actualizer.py** : module stateless qui réveille les voisins des cellules nouvellement ACTIVE/SOLVED (ACTIVE→TO_REDUCE, FRONTIER→TO_PROCESS). Appelé avec explicitement les coordonnées des cellules qui viennent de changer.
> Alerte (hors champ de vision) : si la capture ne couvre pas toutes les voisines UNREVEALED d’une ACTIVE, la frontière est incomplète. Seule la vision peut injecter ces UNREVEALED en storage. Recentrer/capturer à nouveau pour compléter la frontière.

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
- `s49_optimized_solver.py` : orchestrateur (CspManager + reducer + segmentation + CSP + probabilités), avec CSP optionnel selon la stratégie de bypass.
- `facade.py` : définit `SolverAction`, `SolverStats`, `SolverApi`.

## 2. Flux de données

### 2.1 Cycle typique (séquentiel, sans parallélisation)
1. **Storage** fournit :
   - `cells` (bounds)
   - `active_set`
   - `frontier_set`
   - `ZoneDB` (index dérivé par `zone_id` + contraintes) et, en pratique, une vue dérivée `frontier_to_process` = union des cellules FRONTIER dont `FrontierRelevance == TO_PROCESS` (homogène par zone)
2. **s40 state Analyzer** reclasse les `GridCell` (JUST_VISUALIZED→ACTIVE/FRONTIER/SOLVED) et met à jour topo/focus dans storage (il ne construit pas de vue solver).
3. **focus_actualizer (post state analyzer)** : réveille les voisines des cellules nouvellement ACTIVE/SOLVED (voisines ACTIVE→TO_REDUCE, FRONTIER→TO_PROCESS). Appelé avec explicitement les coordonnées des cellules qui viennent de changer.

4. **OptimizedSolver** exécute la résolution dans l’ordre (en consommant la frontière préparée dans storage) :
   - **réduction de frontière systématique** (déterministe) uniquement sur les ACTIVE `TO_REDUCE` ; toutes les ACTIVE traitées passent `REDUCED`
   - **bypass CSP** si la réduction a produit suffisamment d’actions
   - sinon **CSP** sur la frontière marquée `TO_PROCESS`, tout les zones traitées passent en `PROCESSED`

5. **ConstraintReducer** (s42) détecte immédiatement les safe/flag via contraintes locales.
6. **Segmentation + CSP** (s42) résolvent les composantes restantes (si exécuté).
   - Les **zones** sont persistées côté storage.
   - Les **components** sont éphémères (reconstruits au moment de la résolution).
> Note à traiter : le recalcul de frontière côté solver (compute_frontier_from_cells) peut être commenté si l’on consomme directement `frontier_set`/`frontier_to_process` maintenus par s40 + focus_actualizer. Garder le code en archive pour rollback rapide.

7. **Controller** publie :
   - les décisions solver (SAFE/FLAG/GUESS) sous forme d’actions (sans cleanup)
   - un `StorageUpsert` qui met à jour :
     - `cells` (metadata solver)
     - `active_add/remove`, `frontier_add/remove`
8. **focus_actualizer (post solver)** : réveille les voisines des cellules nouvellement ACTIVE/SOLVED après actions solver (même comportement que post-vision).
9. Le **solver** marque `TO_VISUALIZE` (topological_state) sur les cellules qu’il annonce **SAFE** (le logical_state reste UNREVEALED tant que Vision n’a pas relu) et les pousse dans `to_visualize` (set maintenu par s3). L’ActionPlanner consomme ces infos pour recadrer la prochaine Vision.
10. **Cleanup bonus** (activable via `enable_cleanup`, défaut ON) : une fois le solver terminé (réduction + CSP éventuel), un module séparé calcule des cibles de “cleanup” sur les `TO_VISUALIZE` et leurs voisines `ACTIVE`. Ces clics sont hors stats solver/CSP et traités en phase bonus (liste `cleanup_actions` séparée).
11. **GUESS optionnel** (`allow_guess`, défaut ON) : si aucune action sûre n’est trouvée, le solver peut (ou non) produire un `GUESS`. Quand désactivé, aucune guess n’est renvoyée et seules les actions sûres/cleanup sont publiées.

Justification (stratégie actuelle) :

- **Deux modes solver** :
  - mode 1 = **réduction de frontière** (toujours) : règles locales de contrainte (saturation / égalité) très rapides, nécessaires de toute façon avant CSP.
  - mode 2 = **CSP** (optionnel) : appelé uniquement si la réduction n’apporte pas assez d’actions.
- Le solver publie seulement SAFE/FLAG/GUESS (GUESS off par défaut). Pas de priorité “SAFE-first” hors de la logique de réduction : dès qu’une case est déduite SAFE, elle passe en `TO_VISUALIZE` (plus `FRONTIER`) et sera cliquée par l’exécuteur.

- **Heuristiques d’exécution hors solver** : le solver ne produit que des `SolverAction` (SAFE/FLAG/GUESS) ; toute astuce d’exécution (ex: double-clic SAFE, clics opportunistes sur des actives voisines) vit dans s5.

### 2.2 StorageUpsert émis par le solver (actions solver uniquement)

```python
StorageUpsert(
    cells={coord: GridCell(..., topological_state=SolverStatus.TO_VISUALIZE, action_status=ActionStatus.SAFE)},
    active_add={...}, active_remove={...},
    frontier_add={...}, frontier_remove={...},
    to_visualize={safe_cells},
)
# Flags runtime :
# - allow_guess (bool, défaut True) : autorise l’émission de GUESS si aucune action sûre.
# - enable_cleanup (bool, défaut True) : génère la liste cleanup_actions (bonus).
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
   - une zone `PROCESSED` est considérée implicitement comme bloquée 
   - toute zone impactée par une mise à jour (changement de `zone_id`, changement de contraintes) repasse `TO_PROCESS`

8. **Relevance déterministe (FocusLevel)** :
   - si une cellule devient **ACTIVE** (TopologicalState) ou si son voisinage change, alors `ActiveRelevance = TO_REDUCE`
   - si une cellule devient **FRONTIER** (TopologicalState) ou si sa zone/contraintes change, alors `FrontierRelevance = TO_PROCESS` (propagé à toute la zone)
   - une cellule ACTIVE passe `REDUCED` quand la réduction ne produit plus rien dans l’état courant (et peut repasser `TO_REDUCE` si un voisin devient ACTIVE/SOLVED)
   - une cellule FRONTIERE passe `PROCESSED` une fois la zone traitée par le csp (et peut repasser `TO_PROCESS` si un voisin devient ACTIVE/SOLVED ; option envisagée : réactiver toute la zone associée)
   - **Repromotion des focus levels (centralisée dans s45_focus_refresher / focus_actualizer)**

La repromotion des focus levels est déclenchée par les changements topologiques vers :
- `TO_VISUALIZE` (safe à cliquer)
- `SOLVED` (mine confirmée ou nombre résolu)  
- `ACTIVE` (nouvelle information)

**Deux points de repromotion dans le pipeline :**

1. **Post-vision** : Après le reclustering des états dans `s40_states_analyzer/states_recluster.py`
   - Gère les changements topologiques issus de la vision (JUST_VISUALIZED → ACTIVE/SOLVED/FRONTIER)
   - Repromotion des voisines ACTIVES et zones FRONTIER impactées
   - `segmentation=None` (pas de zones disponibles à ce stade)

2. **Post-solver** : Après les actions solver (safe/flag) dans `s49_optimized_solver.py`
   - Gère les changements topologiques issus des résolutions (TO_VISUALIZE/SOLVED)
   - Repromotion avec `segmentation` disponible pour les zones FRONTIERes

   - **cohérence stricte** : `focus_level_active` n’est autorisé que si `solver_status == ACTIVE`; `focus_level_frontier` n’est autorisé que si `solver_status == FRONTIER`; tous les autres états exigent les deux focus à `None` (enforcé par s3 storage).

9. **Actions publiées** :
   - `actions` = SAFE/FLAG/GUESS (GUESS activable via `allow_guess`, défaut ON).
   - `cleanup_actions` = clics bonus sur `TO_VISUALIZE` + voisines `ACTIVE`, séparés des stats solver/CSP, activables via `enable_cleanup` (défaut ON).

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