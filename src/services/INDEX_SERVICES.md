# Services `src/services/` – Index d’orchestration

## Vue d'ensemble
Orchestration runtime capture → vision → solver → action. Chaque service encapsule une couche métier et délègue aux modules `lib/`. Aucun service ne construit de chemins/suffixes overlay : il transmet uniquement `export_root` et les données métier.

---

## Services principaux (pipeline live)

### SessionSetupService (`s1_session_setup_service.py`)
- Démarrage/arrêt du navigateur, sélection mode/difficulté, création `SessionStorage` + `SessionState`.
- `cleanup_session()` appelé uniquement par le pilote principal (prompt Entrée avant fermeture).

### ZoneCaptureService (`s1_zone_capture_service.py`)
- Découverte des canvases (`CanvasLocator`) et capture JS `canvas.toDataURL`.
- Exporte tuiles dans `temp/games/{id}/s1_raw_canvases/`, assemble via `s12_canvas_compositor` vers `s1_canvas/full_grid_*.png`.

### VisionAnalysisService (`s2_vision_analysis_service.py`)
- Centre la vision sur la grille capturée, appelle `CenterTemplateMatcher`.
- Ne sauvegarde plus de captures : attend un `GridCapture.saved_path` fourni par la capture s1. Transmet `export_root` au VisionController ; l’overlay vision est enregistré par `VisionOverlay.save` sous `{base}/s2_vision_overlay/`.

### GameSolverServiceV2 (`s3_game_solver_service.py`)
- Prend `analysis_result` (bounds, matches, stride, cell_size, export_root) et orchestre storage → `CspManager`.
- Passe uniquement `export_root` aux générateurs d’overlays (s491/s492/s493/s494). Aucun nom/suffixe overlay défini ici.

### StorageSolverService (`s3_storage_solver_service.py`)
- Façade storage + solver (OptimizedSolver), expose `solve_snapshot` pour rejouer un snapshot s3.

### GameLoopService (`s5_game_loop_service.py`)
- Boucle de jeu : capture → vision → solver → (optionnel) exécution d’actions.
- Passe `export_root = base_path` (SessionStorage.build_game_paths) à vision/solver ; aucun chemin overlay construit ici.

### ActionExecutorService (`s4_action_executor_service.py`)
- Exécute les actions du solver via NavigationController/JS.

### ActionPlannerController (`lib/s5_actionplanner`) [référence]
- Calcul heatmap/viewport plan à partir de la frontière et des actions (intégrable par s5 quand réactivé).

---

## Dossiers de sortie par partie (SessionStorage.build_game_paths)
- `s1_raw_canvases/` : captures tuiles
- `s1_canvas/` : full_grid composité (capture s1)
- `solver` = `{base}` : racine export_root unique
- Overlays générés par leurs modules sous export_root :
  - `s2_vision_overlay/`
  - `s40_states_overlays/`
  - `s42_segmentation_overlay/`
  - `s42_solver_overlay/`
  - `s43_csp_combined_overlay/`

---

## Notes d’utilisation
- Activer `overlay_enabled=True` dans le pilote pour produire vision + solver overlays.
- Le cleanup de session se fait une seule fois après la boucle principale (main/bot), jamais dans la passe solver.
