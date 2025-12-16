---
description: Feuille de route s4_solver (Grid Analyzer + OptimizedSolver)
---

# PLAN S4 SOLVER – Synthèse & objectifs

Document de travail qui synthétise les exigences du **PLAN DE SIMPLIFICATION RADICALE** et de **SYNTHESE_pipeline_refonte.md** pour la couche s4. Il servira de référence tant que l’implémentation n’est pas finalisée.

## 1. Mission
- Transformer le snapshot s3_storage (cells + sets) en **actions sûres** (clics, drapeaux) et, en parallèle, produire un `StorageUpsert` (métadonnées + sets) sans jamais modifier s3 autrement.
- Consommer les cellules enrichies (`raw_state`, `logical_state`, `number_value`, `solver_status`, `action_status`) et maintenir les transitions **JUST_REVEALED → ACTIVE/FRONTIER → SOLVED**.
- Publier les mises à jour via `StorageUpsert` uniquement : `unresolved_remove`, `frontier_add/remove`, et mises à jour de `solver_status/action_status`.
- Retourner les `SolverAction` à la couche d’orchestration (pipeline principal : services + app), qui décidera de leur exécution (s6) et des recaptures (s1/s2).
- Implémentation actuelle : **s40_grid_analyzer** + **s42_csp_solver** via `s49_optimized_solver.py` (CSP-only). `s41_propagator_solver` reste optionnel/futur.

## 2. Découpage prévu
```
s4_solver/
├─ s40_grid_analyzer/          # snapshot grille + statuts + vues
│   ├─ grid_classifier.py      # JUST_REVEALED → ACTIVE/FRONTIER/SOLVED
│   └─ grid_extractor.py       # vues Frontier + segmentation pour solveurs
├─ s41_propagator_solver/      # motifs déterministes (optionnel/futur)
│   └─ pattern_engine.py
├─ s42_csp_solver/             # segmentation + CSP exact + reducer
│   └─ s420_csp_manager.py ...
├─ controller.py / facade.py   # orchestration & API publique
└─ test_unitaire/              # pipelines debug + overlays
```

## 3. État actuel (couche s4)
La couche s4 est considérée comme implémentée dans sa version actuelle :
- `OptimizedSolver` (CSP-only) orchestre `CspManager.run_with_frontier_reducer()`.
- `SolverController` lit le snapshot storage, exécute le solveur, puis publie :
  - une liste de `SolverAction` (CLICK/FLAG/GUESS),
  - un `StorageUpsert` (`unresolved_remove`, `frontier_add/remove` + métadonnées cellules).

## 4. Phase à venir (priorité) : intégration dans le pipeline principal
Objectif : faire de s4 un maillon “normal” du pipeline, c’est-à-dire appelé depuis l’orchestration de production, pas uniquement via des scripts/tests.

La prochaine phase consiste à câbler la chaîne capture/vision/storage/solver dans :
- `src/services/` (orchestrateurs),
- `src/bot_1000mines.py` (scénarios),
- `src/main.py` (entrypoint CLI).

Points attendus dans `src/services/` :
- Utiliser/étendre `src/services/s3_storage_solver_service.py` comme façade “solve snapshot”.
- Créer ou refactoriser un service d’orchestration qui exécute une itération complète :
  - s1_capture → s2_vision → `storage.upsert(matches_to_upsert(...))` → `StorageSolverService.solve_snapshot()`.
- Clarifier le statut des services legacy (`s5_game_loop_service.py`, `s3_game_solver_service.py`) qui reposent sur `s0_navigation`/`s3_tensor`/`HybridSolver` : ils ne doivent plus être la référence pour V2.

Points attendus dans `src/bot_1000mines.py` :
- Ajouter un mode “pipeline principal” (ex. `run_pipeline_main()`), distinct du `run_minimal_pipeline()`.
- S’appuyer sur les services (et non instancier les contrôleurs directement) pour éviter de dupliquer l’orchestration.

Points attendus dans `src/main.py` :
- Exposer une commande/option CLI permettant de choisir le mode (minimal vs pipeline principal).

## 5. Critères de fin (DoD)
- Le pipeline principal appelle s4 à chaque itération via un service unique dans `src/services/`.
- `src/bot_1000mines.py` et `src/main.py` utilisent ce service sans dupliquer la logique.
- Les sorties sont stables :
  - actions solver exportées,
  - overlays optionnels,
  - storage upsert appliqués (unresolved/frontier/métadonnées).

## 6. Références
- `doc/SPECS/s04_SOLVER.md`
- `doc/SPECS/s03_STORAGE.md`
- `doc/PIPELINE.md`
