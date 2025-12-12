---
description: Chaîne de capture S1
---

# PLAN S1 CAPTURE

## Objectif
Documenter l’interaction entre les couches `s0_interface` et `s1_capture` après la refonte canvas-only, afin que les couches supérieures (solver / services) puissent s’appuyer sur une API unique.

## Vue d’ensemble
```
S2+/Services ➜ InterfaceController (s0) ➜ CaptureController (s1) ➜ CanvasCaptureBackend (JS)
```

- **InterfaceController** (façade s0) centralise navigateur, conversion de coordonnées, navigation et maintenant capture.
- **CaptureController** (s1) orchestre la logique canvas : récupération des métadonnées, découpe, overlay.
- **CanvasCaptureBackend** exécute le `canvas.toDataURL()` et gère les sauvegardes optionnelles.
- **GridOverlayLayer** ajoute un overlay diagnostique optionnel (géré depuis s1).

## API exposée

### Côté InterfaceController
- `capture_zone(request: CaptureRequest) -> CaptureResult`
- `capture_grid_window(grid_bounds, *, save=False, annotate=False, filename=None, bucket=None) -> CaptureResult`

Ces deux méthodes déléguent à `_get_capture_controller()`, qui instancie paresseusement `CaptureController` avec :
- `interface=self`
- `canvas_backend=CanvasCaptureBackend(driver)`
- `viewport_mapper=self.navigator.viewport_mapper`

### Côté s1_capture.api
- `CaptureRequest`: point canvas + taille + options (save, annotate, metadata…)
- `CaptureResult`: image PIL + bytes + infos de sauvegarde
- `CaptureControllerApi`: protocol pour `capture_zone`, `capture_grid_window`, `export_debug_overlay`

## Flux d’exécution
1. Service/Solver appelle `interface.capture_grid_window(bounds, annotate=True)`.
2. `InterfaceController.ensure_visible` s’assure que la zone est à l’écran via NavigationController.
3. Création d’un `CaptureRequest` (point d’origine + taille).
4. `_get_capture_controller()` fournit un `CaptureController` configuré.
5. `CaptureController.capture_zone` :
   - récupère `capture_meta` via `interface.get_capture_meta`
   - calcule `relative_origin` (validation de la zone)
   - appelle `CanvasCaptureBackend.capture_tile`
6. Optionnel : overlay via `GridOverlayLayer` si `annotate_grid=True`.

## Règles d’utilisation
1. **Toujours passer par InterfaceController** pour demander une capture (jamais instancier `CaptureController` directement dans les couches supérieures).
2. **Pas de capture plein écran** : uniquement la zone canvas ciblée.
3. **Sauvegardes disque** :
   - `save=True` + `bucket` (clé dans `PATHS`)
   - sinon résultat en mémoire (PIL + bytes).
4. **Overlay** : activer via `annotate=True` ou appeler `CaptureController.export_debug_overlay` depuis s1 uniquement (s0 ne l’expose plus).

## Points d’extension
- Ajouter d’autres couches d’overlay (statut, heatmap) côté s1 pour debug avancé.
- Brancher un cache d’images ou un pipeline d’analyse directement après `CaptureResult`.
- Étendre `CaptureRequest.metadata` pour tracer l’origine des captures ou les paramètres solver.
