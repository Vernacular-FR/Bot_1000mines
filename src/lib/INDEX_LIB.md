# Bibliothèque `lib/` – Index des modules actifs (pipeline live)

## Vue d'ensemble
Modules techniques utilisés par les services runtime capture → vision → solver. Les dossiers legacy restent pour historique mais ne sont plus dans le chemin critique. La logique (chemins overlay, suffixes, calculs) vit dans ces modules ; les services/controllers ne sont que des passe-plats qui transmettent `export_root` et les données métier.

---

## s0 Interface
- `s00_browser_manager.py` : gestion navigateur (start/stop, exec_script).
- `controller.py`, `s03_game_controller.py` : façade jeu (status, sélection mode).
- `s03_Coordonate_system.py` : `CoordinateConverter`, `CanvasLocator`, `ViewportMapper` (coordonnées CSS/grid).

## s1 Capture
- `s11_canvas_capture.py` : capture JS `canvas.toDataURL`, helpers fallback.
- `s12_canvas_compositor.py` : assemblage tuiles → `full_grid_*.png`, recalcul `grid_bounds`.
- Overlay interface legacy conservé mais non utilisé dans le pipeline principal.

## s2 Vision (actif)
- `s21_template_matcher.py` (CenterTemplateMatcher), manifest central templates.
- `s22_vision_overlay.py` : overlay vision (question_mark blanc, decor gris/noir).
- `s21_templates_analyzer/*` : outils de génération templates/variance.

## s3 Storage (active)
- `controller.py` + `facade.py` : StorageUpsert, GridCell, sets revealed/unresolved/frontier.
- `s32_set_manager.py`, `s31_grid_store.py` : gestion des trois sets, grille sparse.

## s4 Solver (OptimizedSolver CSP-only)
- `s40_grid_analyzer` : `grid_classifier`, `grid_extractor`, `FrontierClassifier`.
- `s42_csp_solver` : `CspManager`, segmentation, reducer, CSP exact, best guess.
- `s49_optimized_solver.py` : orchestrateur CSP-only.
- `s49_overlays/` : `s491_states_overlay`, `s492_segmentation_overlay`, `s493_actions_overlay` (guesses croix blanche, reducer + CSP opaques), `s494_combined_overlay` (zones + actions, applique reducer + CSP).

## Overlays & sorties (par partie)
- export_root = `{base}` (SessionStorage.build_game_paths → clé `solver`)
- Vision overlay : `{base}/s2_vision_overlay/{stem}_vision_overlay.png` (via `VisionOverlay.save`)
- Solver overlays (générés par les modules) :
  - `s40_states_overlays/{stem}_{suffix}.png`
  - `s42_segmentation_overlay/{stem}_segmentation_overlay.png`
  - `s42_solver_overlay/{stem}_solver_overlay.png`
  - `s43_csp_combined_overlay/{stem}_combined_solver.png`

## Legacy (référence uniquement)
- `lib/s2_recognition/*`, `lib/recognition/*` : anciens matchers/overlays couleur.
- `s3_tensor/*` : ancienne base d’état (remplacée par s3_storage).

---

Dernière mise à jour : 15 Décembre 2025 – pipeline live capture→vision→solver aligné sur services et overlays s4_solver.
