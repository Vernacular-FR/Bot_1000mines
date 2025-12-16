# ARCHITECTURE – Référence officielle

Cette spécification décrit l’architecture cible du bot 1000mines après la simplification radicale. Elle constitue la référence unique pour les décisions techniques.

## 1. Vue d’ensemble des couches

1. **s0_interface** – Pilote le navigateur/canvas (DOM, coordonnées). Expose conversion grille↔écran, navigation viewport, clics JS et lecture statut. Doit rester interchangeable (Selenium aujourd’hui, extension demain).
2. **s1_capture** – Récupère l’image via capture directe du canvas (`canvas.toDataURL`) + découpe/capture de tuiles 512×512. L’assemblage aligné est délégué à `src/lib/s1_capture/s12_canvas_compositor.py`.
3. **s2_vision** – Convertit l’image en grille brute via matching déterministe (CenterTemplateMatcher) + overlays PNG/JSON.
4. **s3_storage** – Grille sparse unique `{(x,y) → GridCell}` + trois sets (revealed/unresolved/frontier). Couche passive.
5. **s4_solver** – **s40_grid_analyzer** (statuts + vues) puis **s42_csp_solver** (OptimizedSolver : reducer + segmentation + CSP exact ≤15 variables + probabilités). **s41_propagator_solver** est présent mais reste une étape optionnelle/future.
6. **s5_actionplanner** – Calcule les trajets/viewport plans pour maximiser la frontier visible et prioriser les actions.
7. **s6_action** – Applique les clics/drapeaux (macro-actions) et remonte l’état.

### Schéma pipeline

```
┌─────────────────┐
│ s0 Interface     │ ← pilote le navigateur / canvas (DOM, coords)
├─────────────────┤
│ s1 Capture      │ ← canvas → raw image (bytes)
├─────────────────┤
│ s2 Vision       │ ← CenterTemplateMatcher → grille brute
├─────────────────┤
│ s3 Storage      │ ← Grid global + Frontier + pruning (alimenté par s2)
├─────────────────┤
│ s4 Solver       │ ← PatternEngine + LocalSolver (lit/écrit storage)
├─────────────────┤
│ s5 Pathfinder   │ ← calcule heatmap + trajets (lit storage, pilote s6)
├─────────────────┤
│ s6 Action       │ ← exécute clics/scroll envoyés par solver/actionplanner
└─────────────────┘
```

## 2. Partage des données

- `CaptureMeta` : timestamp, offset viewport, taille de cellule, zoom.
- `GridRaw` : dict[(x,y)] = code int (0 fermé, -1 drapeau, 1..8 num, 9 vide).
- `FrontierSlice` : sous-ensemble compact + densité/priorités + metadata viewport.
- `ActionBatch` : liste ordonnée d’actions sûres (flags/open) avec priorité et contexte.
- `ViewportPlan` : ordres multi-étapes (scroll, zoom, reposition) envoyés par s5 vers s0/s6.

## 3. Précisions clés

- **Capture directe** : priorité au canvas (toDataURL) et CDP. Selenium classique uniquement en secours.
- **Vision déterministe** : LUT calibrée automatiquement au démarrage (scan d’une grille connue). Filtre de stabilité (vote sur captures successives).
- **Storage (3 sets)** : `revealed/unresolved/frontier` sont maintenus via `StorageUpsert`. Vision alimente revealed/unresolved, et la frontière représente les cellules fermées adjacentes aux révélées.
- **Solveur exact** : composants extraites sur la bordure ; backtracking avec pruning (bornes min/max par contrainte). Les actions renvoyées doivent être 100 % sûres.
- **Pathfinder** : doit pouvoir fonctionner même si la vision ne peut pas relire certaines cases (zones hors écran). S’appuie sur densité/frontière pour choisir les déplacements (fonction attracteur à définir).
- **Action** : support des macro-clics, ordonnancement précis, remontée d’état pour mettre à jour storage/vision.
- **Responsabilités strictes** : la logique métier reste au plus bas niveau (modules lib/*). Les controllers sont des passe-plats vers ces modules. Les services orchestrent uniquement le flux (capture → vision → solver) en passant des paramètres bruts (export_root, bounds, matches) sans construire de chemins ou de suffixes.
- **Chemins et export_root** : `SessionStorage.build_game_paths` fournit la racine de partie `{base}` et crée seulement `s1_raw_canvases/`, `s1_canvas/`, `solver` (alias `{base}`). Tous les générateurs d’overlays définissent eux-mêmes leurs sous-dossiers et suffixes sous `export_root = {base}`.
  - Vision overlay : `{base}/s2_vision_overlay/{stem}_vision_overlay.png`
  - States : `{base}/s40_states_overlays/{stem}_{suffix}.png`
  - Segmentation : `{base}/s42_segmentation_overlay/{stem}_segmentation_overlay.png`
  - Actions : `{base}/s42_solver_overlay/{stem}_solver_overlay.png`
  - Combined : `{base}/s43_csp_combined_overlay/{stem}_combined_solver.png`
  - s23 vision→storage délègue à `render_actions_overlay` (même dossier/suffixe).
- **Captures** : la couche capture (s1) doit fournir un `GridCapture.saved_path` prêt. VisionAnalysisService n’écrit plus de fichier ; il lève si la capture n’est pas persistée. VisionController enregistre l’overlay via `VisionOverlay.save` uniquement si `export_root` est fourni.

## 4. Migration Extension

- Préparation Native Messaging : l’extension envoie `capture` / `solve` / `act` au backend Python via JSON.
- Option translation Rust/C++ → WebAssembly pour embarquer la logique côté extension. Décision à prendre après stabilisation complète.
- Overlays conservés (PNG/JSON) pour être ré-exploités dans une UI pédagogique.

## 5. Roadmap (rappel)

Itération 0 : nettoyage + création arborescence s0→s6 + `main_simple.py`.
Itération 1 : s0_interface refactor.
Itération 2 : s1_capture (canvas toDataURL).
Itération 3 : s2_vision (sampler + calibration + debug).
Itération 4 : s3_storage (grille sparse + sets + invariants).
Itération 5 : s4_solver.
Itération 6 : s5_actionplanner.
Itération 7 : s6_action.
Itération 8 : Extension-ready (interfaces isolées, proto Native Messaging).

## 7. Arborescence cible (référence)

```
src/
├─ app/                      # points d’entrée (cli / scripts)
├─ services/                 # orchestrateurs (session, boucle…)
└─ lib/
    ├─ s0_interface/
    │  ├─ facade.py / controller.py           # portes d’entrée
    │  ├─ s01_*, s02_* …                      # toute la logique
    │  └─ __init__.py
    ├─ s1_capture/
    │  ├─ facade.py / controller.py
    │  ├─ s11_*, s12_* …
    │  └─ __init__.py
    ├─ s2_vision/
    │  ├─ facade.py / controller.py
    │  ├─ s21_*, s22_* …
    │  ├─ __init__.py
    │  └─ debug/
    │       ├─ overlay_renderer.py
    │       └─ json_exporter.py
    ├─ s3_storage/
    │  ├─ facade.py / controller.py (aucune logique)
    │  ├─ s31_grid_store.py, s32_frontier_metrics.py, …
    │  ├─ serializers.py
    │  └─ __init__.py
    ├─ s4_solver/
    │  ├─ facade.py / controller.py
    │  ├─ s41_pattern_engine.py, s42_local_solver.py, s43_frontier_analyzer.py, …
    │  ├─ __init__.py
    │  └─ debug/
    │       ├─ overlay_renderer.py
    │       └─ json_exporter.py
    ├─ s5_actionplanner/
    │  ├─ facade.py / controller.py
    │  ├─ s51_viewport_planner.py, s52_action_sequencer.py, …
    │  └─ __init__.py
    ├─ s6_action/
    │  ├─ facade.py / controller.py
    │  ├─ s61_click_executor.py, s62_timing_manager.py, …
    │  └─ __init__.py
    └─ main_simple.py                 # boucle while simple (entry prototype)
```

## 6. Règles d’implémentation

- Chaque dossier `src/sX_*` contient `interface.py` décrivant son contrat officiel.
- Tests unitaires par couche, référencés dans `tests/` avec README spécifique.
- Journaliser les décisions majeures dans `SPECS/DEVELOPMENT_JOURNAL.md` après chaque itération.
- Aucune duplication documentaire : `doc/` = résumés, `SPECS/` = référence technique.

### 6.1 Conventions de nommage
- `facade.py` et `controller.py` sont uniquement des points d’entrée : aucune logique métier.
- Toute logique d’une couche vit dans des fichiers préfixés `sXY_` (ex. `s31_grid_store.py`, `s42_local_solver.py`).
- Les modules de debug/debugging portent des noms explicites (`debug/overlay_renderer.py`, etc.).
- Les tests suivent la convention `tests/test_<couche>_*.py`.
