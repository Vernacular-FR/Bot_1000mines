---
description: Façade s0_interface
---

# PLAN S0 INTERFACE

## Objectif
Décrire la couche `s0_interface`, responsable du pont unique entre Selenium (navigateur) et les couches supérieures (solver / services). Cette couche fournit l’orchestration du navigateur, la conversion de coordonnées, la navigation du viewport, la lecture de statut et l’intégration avec `s1_capture`.

## Vue d’ensemble
```
S2+ / Services
      │
      ▼
  InterfaceController (façade s0)
      ├─ BrowserManager (démarrage/navig.)
      ├─ CoordinateConverter & CanvasLocator
      ├─ NavigationController (déplacements/clics)
      ├─ StatusReader (#status DOM)
      └─ CaptureController (s1) via façade capture_*
```

## Modules principaux

| Module | Rôle clé | Fichiers |
|--------|----------|----------|
| **BrowserManager** | Démarre/arrête Chrome, applique BROWSER_CONFIG, gère navigation et attentes. | `s00_browser_manager.py` |
| **CoordinateConverter** | Calcule les correspondances grille/canvas/écran, maintient l’ancre CSS, expose `canvas_locator`. | `s03_Coordonate_system.py` |
| **CanvasLocator** | Trouve les tuiles canvas (id, position, taille) utilisées par la capture. | `s03_Coordonate_system.py` |
| **NavigationController** | Déplacements viewport (via JS), clics sur canvas ou grille, interactions clavier/souris simulées. | `s03_game_controller.py` |
| **StatusReader** | Lit `#status` (scores, vies, difficulté) via Selenium et renvoie `GameStatus`. | `s05_status_reader.py` |
| **InterfaceController** | Façade publique : compose les composants ci-dessus, expose API simple, assure liaison avec `s1_capture`. | `controller.py` |

## Flux majeurs
1. **Initialisation** (`InterfaceController.from_browser`)  
   - Vérifie que `BrowserManager` a un driver.  
   - Instancie `CoordinateConverter` + `CanvasLocator`, configure l’ancre, construit `NavigationController` & `StatusReader`.  
   - Instancie paresseusement `CaptureController` (s1) avec le driver courant.

2. **Gestion du viewport**  
   - `refresh_state()` lit l’ancre CSS + tente un `locator.locate("0x0")`.  
   - `ensure_visible(grid_bounds)` compare la zone cible avec `viewport_mapper`, puis délègue à `NavigationController.move_viewport`.

3. **Navigation / Actions**  
   - `scroll`, `click_canvas_point`, `click_grid_cell` utilisent `CoordinateConverter` pour transformer les coordonnées et délèguent à `NavigationController`.

4. **Capture**  
   - `capture_zone(request)` / `capture_grid_window(bounds, …)` délèguent à `CaptureController`.  
   - `_get_capture_controller()` crée `CaptureController(interface=self, canvas_backend=CanvasCaptureBackend(driver), viewport_mapper=navigator.viewport_mapper)`.

5. **Lecture du statut**  
   - `read_game_status()` s’appuie sur `StatusReader`, instancié à la demande si nécessaire.

## API exposée (couches supérieures)

- **Etat & viewport**  
  - `refresh_state() -> ViewportState`  
  - `ensure_visible(grid_bounds)`  
  - `locate_canvas_for_point(canvas_x, canvas_y) -> CanvasDescriptor`  
  - `get_capture_meta(canvas_x, canvas_y) -> Dict`

- **Actions & navigation**  
  - `scroll(dx, dy)`  
  - `click_canvas_point(canvas_x, canvas_y)`  
  - `click_grid_cell(grid_x, grid_y)`

- **Capture (façade s1)**  
  - `capture_zone(request: CaptureRequest) -> CaptureResult`  
  - `capture_grid_window(grid_bounds, *, save=False, annotate=False, filename=None, bucket=None) -> CaptureResult`

- **Status**  
  - `read_game_status() -> GameStatus`

## Responsabilités & limites
1. **Interface unique** : aucune couche supérieure ne doit instancier directement `BrowserManager`, `CoordinateConverter`, `NavigationController` ou `CaptureController`. Tout passe par `InterfaceController`.
2. **Faible couplage** : la logique DOM/canvas reste confinée à s0, alors que s1 se limite au traitement des images.
3. **Logs simplifiés** : uniquement des `print` pour erreurs et étapes-clés (conformément aux règles globales).
4. **Pas de fallback legacy** : capture plein écran et systèmes de logs historiques ont été retirés.

## Points d’extension
- Brancher un **ViewportMapper** plus sophistiqué (ex : suivi multi-ancres).  
- Ajouter des helpers `interface.capture_grid_sequence` si besoin de captures multiples alignées.  
- Intégrer un système de **monitoring** (ex : métriques temps de navigation) via hooks optionnels dans la façade.  
- Documenter les scripts de démarrage/négation dans `services/` pour utiliser systématiquement `InterfaceController`.
