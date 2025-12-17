# Plan de mise en conformité du code (vs SPECS archive)

Objectif : aligner le code avec les SPECS archivées mises à jour (vision, storage, solver, session context/overlays).

## 1) Storage (s3) – fondations (invariants + sets auto)
- Fichiers : `GridStore`/`SetManager`/`apply_upsert`
- Enforcer les invariants (pare-feu) :
  - `logical_state != OPEN_NUMBER` ⇒ `number_value = None`
  - Hors ACTIVE/FRONTIER ⇒ `focus_level = None`
  - Cohérence `focus_level` ↔ `solver_status` (ACTIVE↔focus_active, FRONTIER↔focus_frontier)
- Recalcul des sets dans `apply_upsert` (garde-fou passif) :
  - À partir des cellules modifiées, reconstruire `known_set/active_set/frontier_set/to_visualize_set` (pas de calcul topo, frontier fournie par state analyzer).
  - Appliquer ensuite les add/remove explicites fournis dans l’upsert pour compatibilité.
- Purger `TO_VISUALIZE` de `active_set` dans `apply_upsert` (pas de filtration à la lecture).
- État actuel : `apply_upsert` délègue uniquement des add/remove explicites à `SetManager` (add-only pour `to_visualize`, aucune reconstruction). À remplacer par un recalcul auto + diff.

## 2) Vision (s2) – neutralité topo
- Fichier : `src/lib/s2_vision/s23_vision_to_storage.py`
- Actions :
  - Supprimer le calcul opportuniste de `frontier`/`active` dans `matches_to_upsert` ; ne renvoyer que `cells` (statuts).
  - Vision n’écrit plus `known_set` : le passage en `JUST_VISUALIZED` suffira pour que storage reconstruise `known_set` lors d’`apply_upsert`.
- Vérifier que la génération d’overlay reste inchangée.

## 3) Solver – focus_actualizer & pipeline
- Créer un module dédié `focus_actualizer` (ex. `src/lib/s4_solver/s45_focus_actualizer.py`), appelé :
  - Post state analyzer (après reclustering JUST_VISUALIZED→ACTIVE/FRONTIER/SOLVED)
  - Post solver (après actions SAFE/FLAG/GUESS/cleanup)
- `s40_state_analyzer` : se limiter au reclassement topo + repromotions via `focus_actualizer`; pas de construction de vue solver.
- `SolverController` / `OptimizedSolver` : consommer `frontier_set`/`frontier_to_process` préparés par storage/state analyzer ; supprimer le recalcul `compute_frontier_from_cells` (non utilisé par le CSP).

## 4) Frontier view
- Garder `SolverFrontierView` comme implémentation type (frontière + contraintes OPEN_NUMBER), mais l’instancier via un helper/factory côté solver à partir du snapshot storage (frontier_set/to_process à jour).
- S’assurer que la segmentation/CSP utilisent bien `frontier_to_process` (FocusLevel) comme filtre.

## 5) SessionContext / overlays
- Fichier : `s30_session_context.py`
- Ajouter `historical_canvas_path` et le renseigner après capture/assembly (s1).
- Propager ce champ aux services qui génèrent les overlays combined/states/actions.

## 6) CHANGELOG / doc
- Noter dans le changelog : suppression frontière vision, ajout `focus_actualizer`, invariants storage renforcés, ajout `historical_canvas_path`, désactivation (commentaire) du recalcul frontière solver.

## 7) Posture d’implémentation
- Pipeline séquentiel : capture → vision → upsert storage → state analyzer (+ focus_actualizer) → upsert storage → solver (réduction/CSP sur to_process) → upsert solver (+ focus_actualizer) → cleanup → planner → actions.
- Garder en archive le code de recalcul frontière si besoin de rollback, mais le désactiver si l’on consomme `frontier_set`/`frontier_to_process` fournis par storage/state analyzer.
