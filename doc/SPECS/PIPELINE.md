---
description: Vue d’ensemble du pipeline V2 (s0 → s6)
---

# PIPELINE – Vue d’ensemble (V2)

Ce document décrit le pipeline d’exécution du bot, sous une forme alignée sur les plans modules (Mission → Architecture → API → Flux → Plan → KPIs → Références).

## 1. Mission

- Orchestrer une boucle itérative : capture → vision → storage → solver → action planner → action executor → recapture.
- Garder une séparation stricte :
  - s3 stocke (passif)
  - s4 décide (actions + upsert)
  - s5 ordonne et convertit les actions solver en actions exécutables
  - s6 exécute “bêtement”
- Centraliser le contexte runtime (export_root/overlays/capture meta) via `SessionContext`.

## 2. Architecture (runtime)

Service d’orchestration V2 : `src/services/s5_game_loop_service.py`.

```
 s0 Interface
   │
   ▼
 s1 Capture  ──> image(s)
   │
   ▼
 s2 Vision   ──> matches + bounds/stride (aucune frontière topologique, pose JUST_VISUALIZED)
   │
   ▼
 s3 Storage  <── StorageUpsert (vision)
   │
   ▼
 s4 State Analyzer + focus_actualizer (reclustering JUST_VISUALIZED→ACTIVE/FRONTIER/SOLVED + repromotions voisines)
   │
   ▼
 s3 Storage  <── StorageUpsert (post reclustering + repromotions)
   │
   ▼
 s4 Solver (réduction + CSP sur les `to_*`) ──> solver_actions + StorageUpsert (solver) + repromotions (focus_actualizer post solver)
   │
   ▼
 s4 cleanup (phase qui ajoute les cleanup_actions sur TO_VISUALIZE + voisines ACTIVE)
   │
   ▼
 s5 ActionPlanner ──> plan d’actions (ordonnancement)
   │
   ▼
 s6 ActionExecutor ──> exécution JS/DOM
   │
   └──> retour à s1/s2 (recapture)
```

Point V2 important : **exécution des actions via JS** ⇒ les clics peuvent s’appliquer hors écran.
Le viewport sert donc principalement à la **vision** (cadrage capture), pas à “rendre les clics possibles”.

## 3. API / données échangées

- `SessionContext` : `game_id`, `iteration`, `export_root`, `overlay_enabled`, `capture_saved_path`, `capture_bounds`, `capture_stride`, **historical_canvas_path** (pour overlays combined/states/actions).
- `StorageUpsert` : batch unique pour modifier `cells` + index (`revealed/active/frontier`) + ZoneDB.
- `FrontierSlice` : coords frontier (consommé par s4).
- `SolverAction` : `CLICK` / `FLAG` / `GUESS` + `cell` + `confidence` + `reasoning`.
- `PathfinderPlan` (s5) : liste d’actions à exécuter (click/flag/guess).

## 4. Flux de données (séquentiel)

1) **Session init** : création `game_id` + init `SessionContext`.
2) **Capture (s1)** : capture des canvases → image assemblée + bounds/stride.
3) **Vision (s2)** : classification → matches.
4) **Storage (s3)** : `storage.upsert(matches_to_upsert(...))`.
5) **Solver (s4)** :
   - analyse (grid_analyzer)
   - CSP en bloc sur les zones `TO_PROCESS` (quand pertinent)
   - retourne actions + `StorageUpsert` (active/frontier/metadatas)
6) **ActionPlanner (s5)** :
   - priorise (déterministe avant guess)
   - convertit `SolverAction` → `PathfinderPlan`
7) **ActionExecutor (s6)** : exécute les actions.
8) **Recapture** : retour au point 2.

## 5. Plan d’évolution

1) Double-clic SAFE (priorité)
2) Marquage `TO_VISUALIZE` après exécution (re-capture ciblée)
3) FocusLevel persistant (ACTIVE TO_TEST/STERILE, FRONTIER TO_PROCESS/BLOCKED)
4) Stratégies “dumb solver loop” (cliquer les ACTIVE selon FocusLevel, limiter le CSP)
5) Overlays : focus levels + décisions (pilotés par `export_root`)

## 6. Validation & KPIs

- Boucle stable : chaque itération fait exactement un cycle capture→vision→solve→plan→execute.
- Storage cohérent : sets invariants (voir `doc/SPECS/s3_STORAGE.md`).
- Overlays : un seul `export_root` via `SessionContext`.

## 7. Références

- `doc/SPECS/s3_STORAGE.md`
- `src/lib/s3_storage/PLAN_S3_STORAGE.md`
- `src/lib/s4_solver/PLAN_S4_SOLVER.md`
- `src/services/s44_dumb_solver_loop.md`
- `src/lib/s5_actionplanner/PLAN_S5_PATHFINDER.md`
