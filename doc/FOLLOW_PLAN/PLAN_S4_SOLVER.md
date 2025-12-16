---
description: Feuille de route s4_solver (Grid Analyzer + OptimizedSolver)
---


# PLAN S4 SOLVER – Analyse & feuille de route

Document de cadrage de la couche s4 : comment on passe de `s3_storage` (cells + sets) à :

- des **actions** (`SolverAction`) à exécuter par l’orchestration (s5/s6)
- des **mises à jour storage** via `StorageUpsert` (sans jamais modifier s3 autrement)

## 1. Mission

- Lire le snapshot storage (cells + sets) et produire des actions :
  - `CLICK` (safe)
  - `FLAG` (mine certaine)
  - `GUESS` (si nécessaire)
- Maintenir la cohérence “solver-side” :
  - progression `JUST_REVEALED → ACTIVE/FRONTIER → SOLVED`
  - mise à jour de la frontière analytique via `frontier_add/remove`
- Publier les changements uniquement via `StorageUpsert` :
  - `unresolved_remove`
  - `frontier_add/remove`
  - mise à jour de métadonnées cellules (statuts solver / action)
- Exposer au pipeline la matière nécessaire pour s5 :
  - actions déterministes en priorité (le double-clic SAFE est ensuite une stratégie s5)
  - informations de pertinence (FocusLevel) pour limiter le retraitement inter-itérations

## 2. Architecture cible

 s4_solver/
 ├─ s40_grid_analyzer/          # snapshot -> vues solver
 │   ├─ grid_classifier.py      # classification topologique
 │   └─ grid_extractor.py       # extraction de vues + segmentation
 ├─ s41_propagator_solver/      # déterministe (futur)
 ├─ s42_csp_solver/             # CSP + reducer
 ├─ controller.py               # façade “solve snapshot”
 └─ facade.py                   # dataclasses (SolverAction, stats, etc.)

### 2.1 `s40_grid_analyzer` (analyse du snapshot)

Responsabilité : transformer l’état “stocké” (cells + sets) en **vues exploitables** par les solveurs.

- Entrées typiques :
  - `unresolved_set` (cells révélées mais à traiter)
  - `frontier_set` (cells fermées adjacentes)
  - `cells` (données brutes + logiques)
- Sorties attendues :
  - une classification topologique (ACTIVE/FRONTIER/SOLVED/...) en mémoire
  - une ou plusieurs vues “solver-friendly” (ex : `SolverFrontierView`, segmentation par composantes)
  - des informations de contexte minimales (bounds, voisinages, mapping coords→cell)

Sous-modules :
- `grid_classifier.py`
  - calcule les statuts topologiques à partir de `raw_state/logical_state` et du voisinage
  - alimente la logique FocusLevel côté solver (dans les phases suivantes)
- `grid_extractor.py`
  - extrait des structures “petites et denses” à partir de la grille sparse
  - segmente la frontière en composantes/patchs exploitables par s42

### 2.2 `s41_propagator_solver` (déterministe, futur)

Responsabilité : produire des actions sûres “cheap” avant le CSP.

- Entrée : vues de s40 (ACTIVE + FRONTIER)
- Sortie : actions déterministes (`CLICK`/`FLAG`) + mise à jour éventuelle des statuts (metadata)

Note : ce module est optionnel. Tant qu’il est absent, s42 reste le solveur principal.

### 2.3 `s42_csp_solver` (CSP + reducer)

Responsabilité : résoudre les zones frontier “dures” via CSP.

- Entrée : segmentation de s40 (frontier par composantes) + contraintes locales (ACTIVE adjacentes)
- Sortie :
  - `actions` (CLICK/FLAG/GUESS)
  - `reducer_actions` (si produit par le reducer)
  - `StorageUpsert` (au minimum `frontier_add/remove`, `unresolved_remove`, métadonnées)

Important : l’exécution effective des actions (et le double-clic SAFE) n’appartient pas à s42.

### 2.4 `controller.py` (façade s4)

Responsabilité : orchestrer une passe solver.

- Lit le snapshot s3 (via StorageController)
- Appelle s40 puis s41/s42 selon la stratégie
- Retourne un objet résultat unique (actions + upsert + stats)

### 2.5 `facade.py` (contrats)

Responsabilité : exposer des types stables (dataclasses/enums) consommés par :
- services (GameLoop)
- s5_actionplanner
- overlays/debug

## 3. API (facade)

Contrat de principe :

- Entrée : snapshot venant de s3 (`get_cells(bounds)` + `get_frontier()` + `get_unresolved()`)
- Sortie :
  - `actions: list[SolverAction]`
  - `reducer_actions: list[SolverAction]` (si présent)
  - `storage_upsert: StorageUpsert` (unresolved/frontier/metadatas)

Ce contrat doit rester compatible avec `src/services/s5_game_loop_service.py` qui fusionne reducer + solver actions, puis délègue la planification/exécution à s5/s6.

## 4. Flux de données (séquentiel)

Schéma de flux (vue logique) :

 ```
            Snapshot s3 (StorageController)
        cells + unresolved_set + frontier_set
                         │
                         ▼
            s40_grid_analyzer (vues)
        ┌────────────────┴────────────────┐
        │                                 │
        ▼                                 ▼
  grid_classifier                    grid_extractor
 (topologie + base Focus)        (views + segmentation)
        │                                 │
        └──────────────┬──────────────────┘
                       ▼
              controller.py (orchestrateur)
                       │
        ┌──────────────┴───────────────┐
        │                              │
        ▼                              ▼
 s41_propagator_solver (futur)   s42_csp_solver (CSP+reducer)
        │                              │
        └──────────────┬───────────────┘
                       ▼
     Sortie s4 (facade.py) : actions + storage_upsert
        - actions: CLICK/FLAG/GUESS
        - reducer_actions: (optionnel)
        - StorageUpsert: unresolved_remove + frontier_add/remove + metadatas
 ```

1) **Vision → Storage** : `StorageUpsert` avec `cells` + `revealed_add` + `unresolved_add`
2) **SolverController** :
   - lit `unresolved` + `frontier` + cells
   - s40 : calcule les vues (ACTIVE/FRONTIER/SOLVED)
   - s42 : CSP + reducer (sur zones `TO_PROCESS`)
3) **Solver → Storage** : publie `StorageUpsert` (unresolved_remove, frontier_add/remove, métadonnées)
4) **Solver → s5_actionplanner** : publie `SolverAction` (CLICK/FLAG/GUESS)

## 5. Plan d’implémentation

1) **Phase 1 – Contrats & stabilité**
   - S’assurer que les sorties solver sont strictement : actions + upsert
   - Aucun effet de bord (pas de logique s5/s6 dans s4)
2) **Phase 2 – FocusLevel**
   - Alimenter la couche storage/metadata pour encoder la pertinence inter-itérations :
     - ACTIVE : `PENDING/PROCESSED/STERILE`
     - FRONTIER : `TO_PROCESS/PROCESSED/UNSOLVED`
3) **Phase 3 – CSP en bloc**
   - Maintenir une segmentation persistante par zones
   - N’exécuter le CSP que quand le volume `TO_PROCESS` le justifie (seuils définis plus tard)
4) **Phase 4 – Overlays**
   - Les overlays restent optionnels et pilotés via `SessionContext.export_root`

## 6. Validation & KPIs

- Actions déterministes priorisées : CLICK/FLAG sortent avant GUESS
- `StorageUpsert` cohérent : pas de mutation directe des sets hors upsert
- Stabilité : même snapshot → mêmes actions (hors shuffle volontaire s5)
- Temps : CSP limité aux zones pertinentes (pas de recalcul global systématique)

## 7. Références

- `doc/SPECS/s3_STORAGE.md`
- `doc/SPECS/s04_SOLVER.md`
- `doc/PIPELINE.md`
- `src/lib/s4_solver/s44_dumb_solver/s44_dumb_solver_loop.md`
