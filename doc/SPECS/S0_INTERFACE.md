---
description: Façade s0_interface
---

# S00 INTERFACE – Spécification technique

s0_interface est la couche “bordure” : elle est le seul endroit qui connaît le navigateur (Selenium/JS/DOM).

Comme `s3_storage`, elle doit rester simple dans son rôle :
- elle exécute des opérations techniques (cliquer, scroller, capturer)
- elle ne déduit rien sur la grille
- elle ne décide rien sur la stratégie

## 1. Mission

- Piloter l’interface web (canvas, DOM) via une API Python stable.
- Fournir la conversion de coordonnées grille ↔ canvas/écran.
- Exposer une API de capture (déléguée à s1_capture) pour obtenir une image alignée.

## 2. Vue d’ensemble

```
Services
   │
   ▼
InterfaceController (façade s0)
   ├─ BrowserManager
   ├─ CoordinateConverter + CanvasLocator
   ├─ NavigationController (JS)
   ├─ StatusReader
   └─ (façade capture) -> s1_capture
```

## 3. Modules principaux (responsabilités)

- `BrowserManager` : démarrage Chrome, navigation, attente.
- `CoordinateConverter` : conversions grille/canvas/écran, ancre CSS.
- `CanvasLocator` : découverte des tiles canvas.
- `NavigationController` : actions JS (scroll, clics).
- `StatusReader` : lecture du `#status` (scores/vies/difficulté) si nécessaire.
- `InterfaceController` : façade unique qui compose et expose l’API.

## 4. API (ce que les couches supérieures utilisent)

### 4.1 Viewport / coordonnées

- `refresh_state() -> ViewportState`
- `ensure_visible(grid_bounds)`
- `locate_canvas_for_point(canvas_x, canvas_y) -> CanvasDescriptor`
- `get_capture_meta(canvas_x, canvas_y) -> Dict`

### 4.2 Actions navigateur

- `scroll(dx, dy)`
- `click_canvas_point(canvas_x, canvas_y)`
- `click_grid_cell(grid_x, grid_y)`

### 4.3 Capture (façade s1)

- `capture_zone(request: CaptureRequest) -> CaptureResult`
- `capture_grid_window(grid_bounds, *, save=False, annotate=False, filename=None, bucket=None) -> CaptureResult`

### 4.4 Status

- `read_game_status() -> GameStatus`

## 5. Flux majeur (résumé)

1) s0 assure que la zone cible est visible (`ensure_visible`).
2) s1_capture réalise la capture canvas alignée (via les méthodes `capture_*` exposées par s0).
3) Les couches supérieures consomment l’image (s2_vision), puis gèrent storage/solver/planner.

## 6. Optimisations de robustesse (2025-12-20)

### CanvasLocator JavaScript Atomique
- **Problème** : Les `StaleElementReferenceException` survenaient lors des zooms/dézooms car les éléments DOM devenaient invalides entre `find_elements()` et l'accès individuel.
- **Solution** : Implémentation JavaScript atomique dans `locate_all()` qui récupère toutes les infos en un seul appel `execute_script()`.
- **Bénéfices** : Immunité totale aux changements DOM, performance améliorée (1 appel vs N appels).

### Positions Canvas depuis IDs
- **Problème** : Les coordonnées DOM des canvas causaient des décalages spatiaux dans le composite.
- **Solution** : Calcul des positions depuis les IDs (ex: `canvas_0x0` → position (0,0) × 512px).
- **Bénéfices** : Alignement parfait indépendant du viewport, cohérence spatiale garantie.

## 7. Invariants (règles à respecter)

- **Façade unique** : aucune couche supérieure n'instancie directement les composants internes (BrowserManager, NavigationController, …).
- **Pas de logique métier** : aucune notion de `ACTIVE`, `FRONTIER`, `FocusLevel` dans s0.
- **Découplage** : s0 pilote le navigateur; s1 gère l'image; s2 classifie; s3 stocke; s4 décide.
