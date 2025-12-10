# MASTER OPTIMIZATION PLAN — Pipeline S0→S6 (Déc 2025)

Ce document remplace les anciens plans de refactorisation et sert désormais de feuille de route **actionnable** pour faire converger tout le bot vers une pile continue :  
**S0 Navigation → S1 Capture → S2 Vision → S3 Tensor → S4 Solver → S5 Actionneur → S6 Pathfinder**, observabilité comprise.

---

## 1. Contexte & principes
- **Vision cible** : pipeline temps réel, zéro copie inutile, persistance unifiée, instrumentation complète.
- **Stratégie** : itérations courtes, compatibilité ascendante (services existants restent fonctionnels), instrumentation obligatoire à chaque phase.
- **Règles** :
  1. Chaque couche publie un contrat d’API stable avant d’être consommée par la suivante.
  2. Les migrations se font par **adaptateurs** (GridDB ↔ TensorGrid, GameLoop ↔ nouveau S5) pour éviter les big bang.
  3. Les KPIs/perf sont mesurés dès la mise en service partielle (pas d’optimisation « aveugle »).

---

## 2. État courant (Déc 2025)
| Couche | État actuel | Commentaire |
| --- | --- | --- |
| S0 Navigation | `src/lib/s0_navigation/*` + services stabilisés | Alignement complet, API utilisée par services et ActionExecutor |
| S1 Capture | `src/lib/s1_capture/*` opérationnel, overlay combiné unifié | Capture unique + metadata en place |
| S2 Vision | `s2_recognition/template_matching_fixed.py` (SmartScan fixe) | Templates opérationnels, pipeline encore branché sur GridDB |
| S3 Tensor | **À construire** (TensorGrid/Hints/TraceRecorder) | Actuellement `grid_state_db.json` + adaptateurs |
| S4 Solver | `s4_solver/overlays` + segmentation refaits, moteur CSP existant | Besoin de lire TensorGrid, refactor en modules core/csp |
| S5 Actionneur | Services `s4_action_executor_service.py` + GameLoop | Doit migrer vers `lib/s5_actionneur/*` + trace log |
| S6 Pathfinder | Non implémenté (logique heuristique dans GameLoop) | Nécessite densité Tensor, scheduler et vecteurs `(dx,dy)` |

---

## 3. Roadmap progressive

### Phase 0 — Stabilisation ()
- Migration `s0_navigation` / `s1_capture`.
- Template matching fixe + overlays solver.
- Services maintenus (GameLoop, ActionExecutor).  
**Validation** : scénario 4 tourne, overlays & actions produits (logs 2025-12-08).

### Phase 1 — Vision & stockage transitoire ()
- `s2_recognition` branché sur `grid_state_db.json`.
- Génération des overlays segmentation + solver (lib/s4_solver/overlays).
- Préparer dossiers `temp/games/{id}` (s0→s4) avec nomenclature finale.  
**Validation** : run complet, 0 actions perdues, logs + overlays présents.

### Phase 2 — Tensor Core ()
  - Créer `src/lib/s3_tensor/tensor_grid.py` + `hint_cache.py` + `trace_recorder.py`.
  - Scripts migration `grid_state_db.json` → TensorGrid (lecture/écriture).
  - Adaptateurs : `TensorGridWriter` depuis S2, `TensorGridView` pour S4.
  - API `update_region(bounds, codes, confidences, dirty_mask)`.
  - `trace_recorder.capture(tick_id, tensor_snapshot, solver_state)`.
  - KPIs `tensor_updates_per_sec`, `dirty_ratio`.
  - Tests unitaires sur TensorGrid (concurrence, mmap/shared_memory).
  - Mode hybride : GridDB écrit en parallèle jusqu’à bascule complète.

### Phase 3 — Vision branchée Tensor (S2↔S3)
  - S2 écrit directement dans TensorGrid + HintCache (plus de GridAnalysisBuilder).
  - Ajout `frontier_mask` + `usable_mask` dans les updates.
  - Pipelines SmartScan différenciés (full scan vs incremental dirty sets).
  - `s21_templates` (cache NPZ), `s22_matching` (multi-thread), `s22_frontier`.
  - Bench latence (objectif : 3 872 cases en < 2 s stable).
  - KPI `scan_ratio`, `cells_per_second`.
  - Tests de non-régression sur scénarios 3/4.

### Phase 4 — Solver 2.0 (S4)
  - `s4_solver/core/` consomme `TensorGrid.get_solver_view()`. ✅ Fait (déc 2025)
  - `tensor_frontier.py` + cache composants CSP. ✅ TensorFrontier branché + profiling
  - Monte Carlo branché (CPU) + overlay segmentation depuis Tensor. ⏳ À finir (overlays désactivés pour focus perfs)
  - `hybrid_solver.py`, `component_cache.py`, `monte_carlo.py`.
  - Bench solver ×0.5 vs actuelle (actions en <1,5 s sur 80 cases).
  - Couverture tests unitaires (zones synthétiques, mocks TensorGrid).
  - Stats `components_reused`, `actions_found_per_iteration` + profiling TensorFrontier (hash/bounds/label/build/hints).

### Phase 5 — Actionneur & Pathfinder (S5/S6)
  - `lib/s5_actionneur/` : `s51_action_queue.py`, `s52_action_executor.py`, `s53_action_logger.py`.
  - `lib/s6_pathfinder/` : densité Tensor, barycentre, scheduler.
  - GameLoop ne fait plus qu’orchestrer S5/S6 (services historiques gardés pour compat).
  - Trace log structuré (intent, résultat, timestamp).
  - KPIs `actions_success_rate`, `viewport_shift_latency`.
  - Intégration slider `(dx,dy)` → `s0_navigation`.
  - Rejeu partie complète sans double clic (log unique).
  - Pathfinder propose >90% des déplacements (cas no-actions).

### Phase 6 — Ops & Architecture distribuée
  - Séparer Vision / Solver / Pathfinder par process (`multiprocessing.shared_memory`).
  - Ajouter dashboards `metrics.py`, `async_logger`.
  - Préparer headless (Playwright/WebGPU) + pipeline GPU optionnel.
  - `ops/metrics.py`, `ops/async_logger.py`, dashboards minimalistes.
  - `--enable-gpu` flag pour Vision/Solver.
- **Validation** :
  - Bench inter-process, KPIs temps réel, redémarrage à chaud possible.

---

## 4. Backlog détaillé par couche

| Couche | Actions court terme | Pré-requis | Indicateurs |
| --- | --- | --- | --- |
| **S0** | Export `NavigationSession` (mask + viewport) pour Pathfinder | Alignement complet () | Logs `dx/dy`, latence déplacement |
| **S1** | Ajouter `usable_mask` + multi-patch pour zones partielles | TensorGrid prêt à recevoir | `%zone exploitée`, latence capture |
| **S2** | Writer TensorGrid + HintCache, SmartScan incrémental | TensorGrid API stable | `scan_ratio`, `cells/s`, `dirty_sets` |
| **S3** | Implémenter TensorGrid/Hints/Trace | Aucun (phase 2) | `tensor_updates_per_sec`, taille snapshots |
| **S4** | Lire TensorGrid, cache composants, MC CPU | HintCache opérationnel | `actions_found`, `solver_time` |
| **S5** | Queue + executor + logger | TensorGrid trace + GameLoop adaptateur | `actions_success_rate`, logs append-only |
| **S6** | Density analyzer + barycentre + scheduler | TensorGrid densité + logger S5 | `viewport_shift_latency`, nb replays |
| **Ops** | Metrics/Async logger, replays `.npz` | TraceRecorder fonctionnel | KPI temps réel, export `.npz` |

---

## 5. Détail de migration (héritage de `MIGRATION_TO_MASTER_PLAN.md`)

> Cette section consolide l'ancien fichier `docs/MIGRATION_TO_MASTER_PLAN.md`. Les tâches sont maintenues ici comme checklist opérationnelle par phase.

### Pré-phase — Stabilisation S0/S1
- **Objectifs** : navigation centralisée, capture patchée, adaptateurs GridDB↔Tensor, Pathfinder v0.
- **Tâches clés** :
  - Extraire `NavigationSession`, conserver un `InterfaceMask`.
  - Déplacer `ZoneCaptureService` vers `lib/s1_capture`, introduire `CapturePatch`.
  - Créer `grid_db_to_tensor.py` + script `scripts/migrate_griddb_to_tensor.py`.
  - Prototyper `lib/s6_pathfinder/pathfinder_v0.py` et l’option `use_pathfinder`.
- **Validation** : scénarios 1 & 4 OK, script de migration tourné, pathfinder activable.

### Phase A — Noyau Tensor (S3)
- **Objectifs** : livrer `TensorGrid`, `HintCache`, `TraceRecorder`.
- **Tâches clés** :
  - API `update_region`, `mark_dirty`, `get_solver_view`.
  - HintCache pour dirty sets, TraceRecorder `.npz`.
  - Adaptateur solver lisant TensorGrid (fallback GridDB).
- **Validation** : tests TensorGrid, migration exécutée sur 2 parties, scénario 4 consomme la vue tensor.

### Phase B — Vision alignée Tensor (S2)
- **Objectifs** : SmartScan écrit TensorGrid directement, masques frontier/usable.
- **Tâches clés** :
  - Modules `s21_templates`, `s22_matching`, `s22_frontier`, `s23_logger`.
  - `CapturePatch` enrichi (usable mask), flag `--use-new-vision`.
- **Validation** : bench latence, TensorGrid rempli sans passer par GridDB, scénario 4 complet.

### Phase C — Solver 2.0 (S4)
- **Objectifs** : solver tensor-native (`tensor_frontier`, caches CSP, MC consolidé).
- **Tâches clés** :
  - Refonte `lib/s4_solver`, nouveaux tests `test_solver_frontier.py`, `test_solver_csp.py`.
  - GameSolverService consomme la nouvelle API (frontier mask, HintCache). ✅
  - Profiling TensorFrontier exposé (`hash`, `bounds`, `label`, `build`, `hint`, `cache_hit`). ✅
  - Monte Carlo + component cache à finaliser.
- **Validation** : gain >40 % temps solver, aucune régression scénario 1/4 (scénario 4 déjà rejoué sans overlays, KPIs TensorFrontier visibles).

### Phase D — Actionneur, Pathfinder, Ops (S5/S6)
- **Objectifs** : files d’actions dédiées, pathfinder complet, instrumentation.
- **Tâches clés** :
  - `s51_action_queue`, `s52_action_executor`, `s53_action_logger`.
  - `s61_density_analyzer`, `s62_path_planner`, `s63_viewport_scheduler`.
  - `metrics.py`, `async_logger.py`, boucle `game_loop_v2`.
- **Validation** : scénario 4 via `game_loop_v2`, KPI visibles dans `dashboards/metrics.db`.

### Phase D bis — Retrait services legacy
- **Objectifs** : supprimer dépendance `src/services`.
- **Tâches clés** :
  - Réécrire `Minesweeper1000Bot` pour utiliser `lib/s5-s6`.
  - Archiver puis retirer les services, mettre à jour README/specs.
- **Validation** : scénarios fonctionnent sans services historiques, diff final contrôlé.

### Phase E — Architecture distribuée (optionnel)
- **Objectifs** : workers Vision/Solver/Pathfinder séparés (IPC shared memory).
- **Tâches clés** :
  - `tensor_ipc.py`, workers dédiés, CLI de contrôle.
- **Validation** : latences inter-process mesurées, redémarrage worker sans interrompre la boucle.

### Checklist récapitulative
- [ ] Pré-phase : S0/S1 stabilisés + adaptateurs + Pathfinder v0.
- [ ] Phase A : TensorGrid + HintCache + TraceRecorder.
- [ ] Phase B : Vision SmartScan branchée Tensor.
- [ ] Phase C : Solver 2.0.
- [ ] Phase D : Actionneur + Pathfinder + Ops.
- [ ] Phase D bis : retrait services legacy.
- [ ] Phase E : architecture distribuée.

---

## 6. Pilotage & validations
1. **Critères de sortie par phase**  
   - Checklist « code livré + KPI + scénario 4 OK ».  
   - Documenter dans `docs/meta/changelog.md` + README services/lib.
2. **Revue hebdo**  
   - État TensorGrid, latence Vision, nb actions solver.  
   - Décider ouverture phase suivante uniquement si KPI OK.
3. **Compatibilité**  
   - Adaptateurs GridDB ↔ Tensor actifs tant que GameLoop dépend des anciens formats.
   - Services historiques supprimés uniquement après phase 5.

---

## 7. Risques & garde-fous
| Risque | Mitigation |
| --- | --- |
| TensorGrid trop volumineux | Fenêtre glissante, compaction lors des scrolls |
| Solvers concurrents sur TensorGrid | API read-only + verrous fins sur dirty flags |
| Actionneur dé-synchronisé | Trace log obligatoire + validation post-action |
| Pathfinder erratique | Toujours fournir fallback heuristique (current GameLoop) |
| Multi-process instable | Phase 6 uniquement après KPIs stables + tests de reconnexion |

---

## 7. R&D / Horizon 2026 (post phases 0→6)
- Vision GPU (FFT/corrélation CUDA, ViT).  
- Neural solving (self-play, TorchScript).  
- #SAT / Model counting sur `TensorFrontier`.  
- JIT / Rust/PyO3 pour sections critiques.  
- Trace learning (datasets `.npz` + décisions solver).
