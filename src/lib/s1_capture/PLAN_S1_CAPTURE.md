# PLAN S1_CAPTURE

## 0. Cadre & objectifs
- S1 capture = couche stateless qui transforme les instructions du contrôleur en bitmaps alignés sur la grille.
- S0 viewport reste unique source pour offsets/canvas et pour le statut interface (scores/vies dans `#status`).
- Capture principale = `canvas.toDataURL()` (mosaïque 512x512), plein écran réservé au debug.

## 1. Audit de l'existant
1. `screenshot_manager.py`
   - À archiver (legacy plein écran). Seuls les utilitaires d'écriture disque survivent.

## 2. Architecture cible (fichiers)
- `api.py`
  - `CaptureRequest`: zone CanvasSpace, options (mode, overlay, format).
  - `CaptureResult`: image (bytes/PIL), `canvas_id`, `relative_origin`, `cell_size`, horodatage.
- `controller.py`
  - Façade publique : `prepare_request()`, `capture_zone(request)`, `capture_grid_window(bounds)`, `export_debug_overlay(result)`.
  - Dependencies injectées : `InterfaceControllerInterface`, `CanvasCaptureBackend`, `GridOverlayService` (optionnel).
- `canvas_capture.py`
  - `CanvasCaptureBackend` (Selenium execute_script + toDataURL, conversions Base64 → PIL/bytes).
- `grid_overlay.py`
  - `GridOverlayLayer` (hérité), `OverlayAssembler` (ajoute légende + export).
- `__init__.py` pour exposer `CaptureController` et dataclasses.

## 3. Modes de capture
1. **CanvasTile** (par défaut)
   - Entrée : `CaptureRequest` avec `canvas_x/canvas_y` (grille ou canvas) → `InterfaceController.get_capture_meta()` → injection offsets → JS `canvas.toDataURL()`.
2. **CanvasMosaic** (option)
   - Balaye plusieurs tuiles (par ex. 2x2) ; compose image côté Python (Pillow) si demandé.
3. **(supprimé)** : plus de capture plein écran, le mode debug reste basé sur `canvas.toDataURL()` + overlays.

## 4. Overlays & diagnostics
- `GridOverlayService` reçoit `CaptureResult` + `ViewportMapper` (optionnel) et génère PNG annoté.
- Les overlays UI sont abandonnés ; seules les grilles + axes sont supportées.
- Intégrer un flag `request.debug.overlay` qui déclenche : sauvegarde raw + overlay dans `PATHS['diagnostics']`.

## 5. Tâches concrètes
1. Écrire `api.py` (dataclasses + Protocol `CaptureControllerInterface`).
2. Implémenter `canvas_capture.CanvasCaptureBackend` (Selenium → CanvasDataURL) sans fallback
3. Créer `controller.py` avec orchestration + options debug.
4. Connecter `InterfaceController.get_capture_meta()` à S1 pour sélectionner la tuile correcte.
5. Documenter dans `PLAN_SIMPLIFICATION radicale.md` la nouvelle structure S1 + lien lectures score/vies depuis s0.

## 6. Dépendances & notes
- S0 doit exposer un `status_reader` pour `#status` (modes, high score, score courant, nombre de vies). Règle lives: +1 vie / palier score précisé dans s0 docs.
- Préparer la transition future : backend JS (extension) devra respecter cette API ; limiter l'usage de Selenium à l'implémentation actuelle.
- Tous les artefacts (captures, overlays) vont sous `PATHS['captures']`, 
