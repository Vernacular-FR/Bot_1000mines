# Bibliothèque `lib/` – Index des modules (Architecture Alternative A)

## Vue d'ensemble

Architecture **"Modular Pipeline"** avec modules purs découplés. Chaque module a une responsabilité claire et des contrats I/O explicites. Pipeline unidirectionnel : `capture → vision → storage → solver → planner → executor`.

---

## s0_browser – Gestion Navigateur
- `browser.py` : `BrowserManager`, `start_browser()`, `stop_browser()`, `navigate_to()`
- `types.py` : `BrowserConfig`, `BrowserHandle`

## s0_coordinates – Conversion Coordonnées
- `converter.py` : `CoordinateConverter`, `grid_to_screen()`, `screen_to_grid()`
- `viewport.py` : `ViewportMapper`, `get_viewport_bounds()`
- `canvas_locator.py` : `CanvasLocator`, localisation des canvas 512×512
- `types.py` : `Coord`, `ScreenPoint`, `CanvasPoint`, `GridBounds`, `ViewportInfo`

## s1_capture – Capture Canvas
- `capture.py` : `CanvasCaptureBackend`, `capture_canvas()`, `capture_zone()`
- `types.py` : `CaptureInput`, `CaptureResult`

## s2_vision – Reconnaissance Visuelle
- `vision.py` : `VisionAnalyzer`, `analyze()`, `analyze_grid()`
- `matcher.py` : `CenterTemplateMatcher`, classification par templates centraux
- `types.py` : `VisionInput`, `VisionResult`, `CellMatch`, `MatchResult`

## s3_storage – État du Jeu (inchangé)
- `controller.py` + `facade.py` : StorageUpsert, GridCell
- `s32_set_manager.py`, `s31_grid_store.py` : grille sparse, sets revealed/active/frontier

## s4_solver – Résolution (Reducer + CSP)
- `solver.py` : `Solver`, `solve()` – orchestrateur principal
- `reducer.py` : `FrontierReducer` – déduction logique simple
- `csp.py` : `CspSolver` – résolution par contraintes
- `types.py` : `SolverInput`, `SolverOutput`, `SolverAction`, `ActionType`

## s5_planner – Planification Actions (module métier)
- `planner.py` : `Planner`, `plan()` – ordonnancement FLAG > CLICK > GUESS
- `types.py` : `PlannerInput`, `ExecutionPlan`, `PlannedAction`

## s6_executor – Exécution Actions
- `executor.py` : `Executor`, `execute()` – exécution via JavaScript
- `types.py` : `ExecutorInput`, `ExecutionResult`

## s7_debug – Debug & Overlays
- `overlays.py` : `OverlayRenderer`, `render_vision_overlay()`, `render_solver_overlay()`
- `logger.py` : `DebugLogger`, `log_iteration()`, `log_action()`

---

## Legacy (*_old) – Référence uniquement
- `s0_interface/` : ancienne façade interface
- `s1_capture_old/` : ancienne capture
- `s2_vision_old/` : ancien vision (contient templates_analyzer)
- `s4_solver_old/` : ancien solver CSP
- `s5_actionplanner_old/` : ancien planner
- `s6_action_old/` : ancien executor

---

Dernière mise à jour : 18 Décembre 2025 – Refactoring Alternative A (Modules Purs Découplés)
