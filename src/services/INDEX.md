# Index des Services - Bot Minesweeper 1000mines

## Vue d'ensemble

Le dossier `services/` contient les services d'orchestration qui coordonnent les interactions entre les modules techniques de `lib/`. Chaque service a une responsabilité spécifique et fournit une interface de haut niveau pour les scénarios.

---

## Services d'Orchestration

### NavigationService
- **path**: services/s1_navigation_service.py
- **type**: Service de navigation et déplacement
- **methods**:
  - `__init__(driver, session_service)` - Initialise avec WebDriver et session
  - `move_viewport(dx, dy, wait_after=1.0)` - Déplace la vue en déléguant à `MineSweeperBot.move_viewport`
- **dependencies**: lib.s0_navigation.game_controller, lib.s0_navigation.coordinate_system
- **features**: Auto-configuration (anchor préparé lors du setup), journalisation détaillée, réutilise la logique compensée centralisée dans `lib/`

### SessionSetupService
- **path**: services/s1_session_setup_service.py
- **type**: Service de configuration de session
- **methods**:
  - `__init__(auto_close_browser=True)` - Initialise le service
  - `setup_session(difficulty=None)` - Configure la session complète
  - `get_driver()` - Retourne l'instance WebDriver
  - `get_bot()` - Retourne l'instance MineSweeperBot
  - `get_coordinate_system()` - Retourne le système de coordonnées
  - `cleanup_session()` - Nettoie la session
- **dependencies**: lib.s0_navigation.browser_manager, lib.s0_navigation.game_controller
- **features**: Configuration complète, gestion automatique, centralisation

### ZoneCaptureService
- **path**: services/s1_zone_capture_service.py
- **type**: Service de capture d'écran
- **methods**:
  - `__init__(driver, paths=None, game_id=None)` - Initialise avec WebDriver, chemins personnalisés et game_id
  - `capture_game_zone_inside_interface(session_service)` - Capture la zone interne (entre cellules limites)
  - `capture_window(filename=None)` - Capture simple de la fenêtre (réutilisée par toutes les variantes)
  - `capture_window_with_combined_overlay(filename=None, grid_bounds=(-30, -15, 30, 15))` - Relance `capture_window` puis génère l'overlay combiné
- **dependencies**: lib.s1_capture.screenshot_manager, lib.s1_capture.combined_overlay, lib.s1_capture.interface_detector
- **features**: API simple (capture unique + overlay optionnel), intégration native avec `GameSessionManager` / `temp/games/{game_id}`

### OptimizedAnalysisService
- **path**: services/s2_optimized_analysis_service.py
- **type**: Service d'analyse visuelle optimisée
- **methods**:
  - `__init__(generate_overlays=True, paths=None)` - Initialise le service avec options
  - `analyze_from_path(image_path, zone_bounds=None)` - Analyse une image depuis un chemin
  - `analyze_existing_screenshots_optimized(generate_overlays=None, zone_bounds=None, generate_report=True)` - Analyse batch optimisée
  - `analyze_single_screenshot_optimized(file_path, generate_overlays=True, zone_bounds=None)` - Analyse une capture unique
  - `build_cell_state_index(zone_bounds, with_metrics=False)` - Expose l'index d’état des cellules (lecture GridDB + métriques)
- **dependencies**: lib.s1_capture.screenshot_manager, lib.s2_recognition.template_matching_fixed, lib.s3_tensor.grid_state (GamePersistence + GridDB)
- **features**:
  - Template matching fixe (OpenCV primaire + fallback hybride) avec statistiques runtime/shadow compare.
  - Pipeline incrémental multi-passes :
    1. **Pass00 – `unrevealed_check`** : matching ciblé sur les `truly_unknown_cells`.
    2. **Pass01 – `empty_refresh`** : déduction logique (pas de matching) qui marque `empty` toutes les candidates non adjacentes aux `unrevealed`.
    3. **Pass02 – `numbers_refresh`** : matching des nombres uniquement sur la frontière restante.
  - Génération d’overlays par passe (optionnelle) + `analysis_diff.json`.
  - Log des métriques : `cells_scanned`, `cells_skipped`, `scan_ratio`, `pass_metrics`, backend de template matching et utilisation du fallback.
  - Persistance immédiate dans GridDB après chaque passe pour que GameSolverService consomme des états cohérents.

### GameSolverService
- **path**: services/s3_game_solver_service.py
- **type**: Service de résolution CSP
- **methods**:
  - `__init__(paths=None)` - Initialise avec chemins personnalisés
  - `solve_from_db_path(db_path, zone_path=None)` - Résout depuis une base de données
  - `convert_actions_to_game_actions(solve_result)` - Convertit les actions en GameAction
- **dependencies**: lib.s3_tensor.grid_state (GridDB, GamePersistence), lib.s4_solver.core/*, lib.s4_solver.overlays/*
- **features**: Backtracking, segmentation en zones, overlays solver/segmentation centralisés dans `temp/games/{game_id}/s3_solver`

### ActionExecutorService
- **path**: services/s4_action_executor_service.py
- **type**: Service d'exécution d'actions
- **methods**:
  - `__init__(coordinate_system, driver)` - Initialise avec système de coordonnées
  - `execute_action(action)` - Exécute une action unique
  - `execute_batch(actions)` - Exécute une liste d'actions
- **dependencies**: lib.s0_navigation.game_controller (API `execute_game_action`), lib.s0_navigation.coordinate_system
- **features**: Conversion GameAction → clics via `MineSweeperBot`, stats d'exécution, support des doubles clics

### GameLoopService
- **path**: services/s5_game_loop_service.py
- **type**: Service de boucle de jeu complète
- **methods**:
  - `__init__(session_service, max_iterations=100, iteration_timeout=30, delay_between_iterations=1.5)` - Initialise avec session et paramètres
  - `execute_single_pass()` - Exécute une seule passe (capture, analyse, solve, act)
  - `play_game()` - Joue une partie complète avec plusieurs passes
  - `_detect_game_state(analysis_result)` - Détecte victoire/défaite/jeu en cours
  - `get_stats()` - Retourne les statistiques globales
  - `reset_stats()` - Remet à zéro les statistiques
- **dependencies**: ZoneCaptureService, OptimizedAnalysisService, GameSolverService, ActionExecutorService, lib.s3_tensor.grid_state.GamePersistence
- **features**: Structure `temp/games/{game_id}` gérée automatiquement (actions, metadata, grid_db), stats centralisées

### TestPatternsService
- **path**: services/s3_test_patterns_service.py
- **type**: Service de test de patterns
- **methods**:
  - `__init__(driver, session_service)` - Initialise avec WebDriver et session
  - `test_viewport_corners()` - Place des drapeaux sur les 4 coins
- **dependencies**: lib.s0_navigation.game_controller, lib.s0_navigation.coordinate_system
- **features**: Tests uniquement, patterns de drapeaux, isolation

---

## Flux d'Utilisation

> Tous les scénarios 1, 3 et 4 commencent par `Minesweeper1000Bot.run_initialization_phase()`,
> qui encapsule `SessionSetupService.setup_session()`, la navigation initiale et la génération
> de l'overlay combiné via `ZoneCaptureService`.

### Scénario 1 : Initialisation + Overlay combiné
1. `run_initialization_phase()` – Configuration, navigation (NavigationService), overlay combiné.
2. `ZoneCaptureService.capture_window_with_combined_overlay()` – Vérification visuelle.

### Scénario 2 : Analyse Locale (offline)
1. `OptimizedAnalysisService.analyze_existing_screenshots_optimized()` – Analyse batch depuis `temp/games/`.
2. `GameSolverService` est optionnel pour rejouer les bases de données existantes.

### Scénario 3 : Jeu Automatique (Passe unique)
1. `run_initialization_phase()` – Préparation de la session.
2. `GameLoopService.execute_single_pass()` – Pipeline capture → analyse → solve → actions.
   - `ZoneCaptureService` pour l'image interne.
   - `OptimizedAnalysisService` + `GameSolverService` + `ActionExecutorService` pour la passe.

### Scénario 4 : Boucle de Jeu Complète
1. `run_initialization_phase()` – Préparation identique au scénario 3.
2. `GameLoopService.play_game()` – Boucle automatique jusqu'à `victory`, `defeat` ou `no_actions`.
   - Réutilise la même session (`game_session`) pour persister `grid_state_db`, overlays et métadonnées.

---

## Architecture des Services

### Principe de Conception
- **Une responsabilité = un service** : Chaque service a une mission claire
- **Interface simple** : Méthodes de haut niveau, abstraction des détails techniques
- **Auto-configuration** : Les services récupèrent leurs dépendances automatiquement
- **Gestion d'erreurs** : Messages clairs et fallbacks appropriés

### Dépendances Hiérarchiques
```
services/
├── SessionSetupService (racine - configuration complète)
│   ├── NavigationService (déplacements de vue via MineSweeperBot)
│   ├── ZoneCaptureService (captures d'écran + game_id)
│   │   └── ScreenshotManager + CombinedOverlay (lib.s1_capture)
│   ├── OptimizedAnalysisService (analyse IA + GridDB)
│   │   └── GamePersistence / GridDB (lib.s3_tensor)
│   ├── GameSolverService (résolution CSP)
│   │   ├── GridDB (lib.s3_tensor)
│   │   └── Composants CSP et overlays (lib.s4_solver)
│   ├── ActionExecutorService (exécution des actions)
│   │   └── MineSweeperBot.execute_game_action (lib.s0_navigation)
│   ├── GameLoopService (orchestration complète)
│   │   ├── ZoneCaptureService
│   │   ├── OptimizedAnalysisService
│   │   ├── GameSolverService
│   │   ├── ActionExecutorService
│   │   └── GamePersistence (lib.s3_tensor)
│   └── TestPatternsService (tests de validation)
```

### Modules techniques sous-jacents
```
lib/
├── s0_navigation/ (browser_manager, game_controller, coordinate_system, navigation_session)
├── s1_capture/ (screenshot_manager, combined_overlay, interface_detector)
├── s2_recognition/ (template_matching_fixed, mapper, types)
├── s3_tensor/ (cell, grid_state, mapper, persistence)
└── s4_solver/
    ├── core/ (GridAnalyzer, GridState wrapper, Segmentation)
    ├── csp/
    └── overlays/ (solver_overlay_generator, segmentation_visualizer)
```

---

## Visualisations des Liens et Dépendances

### Flux de Données - Architecture en Couches

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Scénarios     │───▶│   Services       │───▶│   Librairies    │
│ (bot_1000mines) │    │ d'Orchestration  │    │   Techniques    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Interface     │    │   Coordination   │    │   Implémentation│
│ Utilisateur     │    │   Métier         │    │   Technique     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Diagramme de Flux - Scénario 5 (Passe Unique)

```
SessionSetupService ────▶ GameLoopService.execute_single_pass()
        │                               │
        ▼                               ▼
    Configuration                  ┌─── Capture ───┐
    Navigation                     │ ZoneCapture   │
                                   │ Service       │
                                   └───────────────┘
                                           │
                                           ▼
                                   ┌─── Analyse ───┐
                                   │ Optimized     │
                                   │ Analysis      │
                                   │ Service       │
                                   └───────────────┘
                                           │
                                           ▼
                                   ┌─── Résolution ─┐
                                   │ GameSolver    │
                                   │ Service       │
                                   └───────────────┘
                                           │
                                           ▼
                                   ┌─── Exécution ──┐
                                   │ ActionExecutor│
                                   │ Service       │
                                   └───────────────┘
```

### Diagramme de Flux - Scénario 6 (Boucle Complète)

```
SessionSetupService ────▶ GameLoopService.play_game()
        │                               │
        ▼                               ▼
    Configuration                  ┌─────────────────────┐
                                   │ Boucle Itérative    │
                                   │                     │
                                   │  ┌─────────────┐    │
                                   │  │execute_     │    │
                                   │  │single_pass()│    │
                                   │  └─────────────┘    │
                                   │         │           │
                                   │         ▼           │
                                   │  ┌─────────────┐    │
                                   │  │ Capture +   │    │
                                   │  │ Analyse +   │    │
                                   │  │ Solve +     │    │
                                   │  │ Execute     │    │
                                   │  └─────────────┘    │
                                   │         │           │
                                   │  ◄── État? ───┘    │
                                   │  Victoire/Défaite  │
                                   └─────────────────────┘
                                           │
                                           ▼
                                   Métadonnées Partie
                                   Structure Fichiers
```

### Matrice des Dépendances Fonctionnelles

```
Services →         Sess Nav  Zone OptA Game ActE Game Test
                    ion     Cap  Ana Solv Exe  Loop Patt

SessionSetup        ─── ─── ─── ─── ─── ─── ─── ─── ───
Navigation          ●   ─── ─── ─── ─── ─── ─── ─── ───
ZoneCapture         ●   ─── ─── ─── ─── ─── ─── ─── ───
OptimizedAnalysis   ●   ─── ─── ─── ─── ─── ─── ─── ───
GameSolver          ●   ─── ─── ─── ─── ─── ─── ─── ───
ActionExecutor      ●   ─── ─── ─── ─── ─── ─── ─── ───
GameLoop            ●   ●   ●   ●   ●   ●   ─── ─── ───
TestPatterns        ●   ─── ─── ─── ─── ─── ─── ─── ───

● = Dépendance directe
─── = Pas de dépendance
```

### Flux de Données Dynamique - Passe Unique

```
┌─────────────────────────────────────────────────────────────┐
│                   ZONE CAPTURE SERVICE                      │
├─────────────────────────────────────────────────────────────┤
│  Input:  Interface du jeu (Selenium WebDriver)              │
│  Output: {game_id}_zone_*.png                               │
│                                                             │
│  Driver ──▶ ScreenshotManager.capture_viewport()             │
│           ──▶ capture_between_cells(game_id)               │
│           ──▶ Image.crop()                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              OPTIMIZED ANALYSIS SERVICE                    │
├─────────────────────────────────────────────────────────────┤
│  Input:  {game_id}_zone_*.png                               │
│  Output: {game_id}_analysis_*.json                          │
│                                                             │
│  Image ──▶ GridDB (mémoire) ──▶ Analyse IA                 │
│         ──▶ Cell Recognition ──▶ Symbol Detection          │
│         ──▶ Grid Analysis ──▶ Export JSON                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 GAME SOLVER SERVICE                         │
├─────────────────────────────────────────────────────────────┤
│  Input:  {game_id}_analysis_*.json                           │
│  Output: GameAction[] + solver overlay PNG                  │
│                                                             │
│  JSON ──▶ GridDB.load() ──▶ CSP Engine                     │
│        ──▶ Segmentation en Zones ──▶ Backtracking          │
│        ──▶ Contraintes ──▶ Solutions ──▶ GameAction[]      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              ACTION EXECUTOR SERVICE                        │
├─────────────────────────────────────────────────────────────┤
│  Input:  GameAction[]                                       │
│  Output: {game_id}_actions_*.json                           │
│                                                             │
│  GameAction[] ──▶ CoordinateSystem.transform()             │
│               ──▶ JavaScript MouseEvent                    │
│               ──▶ Selenium click()                          │
└─────────────────────────────────────────────────────────────┘
```

### Flux de Base de Données - Cycle Complet

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   IMAGE PNG     │───▶│   GRIDDB (JSON)  │───▶│   ACTIONS JSON  │
│                 │    │                  │    │                 │
│ {game_id}_      │    │ {game_id}_       │    │ {game_id}_      │
│ zone_*.png      │    │ analysis_*.json  │    │ actions_*.json  │
│                 │    │                  │    │                 │
│ - Pixels        │    │ - Cells[]        │    │ - Actions[]     │
│ - Dimensions    │    │ - Types[]        │    │ - Types[]       │
│ - Timestamp     │    │ - Confidence[]   │    │ - Coordinates[] │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SCREENSHOT    │    │   GRID STATE     │    │   EXECUTION     │
│   MANAGER       │    │   DATABASE       │    │   LOGS          │
│                 │    │                  │    │                 │
│ capture_viewport│    │ load/save()      │    │ execute_batch() │
│ crop()          │    │ get_summary()    │    │ performance()   │
│ save()          │    │ update_cell()    │    │ results()       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Cycle de Vie des Données par Partie

```
PARTIE {game_id}
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│ 1. CAPTURE                                              │
│    ScreenshotManager ──▶ viewport.png                    │
│    ──▶ zone.png ──▶ {game_id}_zone_*.png               │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│ 2. ANALYSE                                              │
│    GridDB (temporaire) ──▶ Analyse IA                  │
│    ──▶ {game_id}_analysis_*.json                        │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│ 3. RÉSOLUTION                                           │
│    GridDB.load() ──▶ CSP Engine                        │
│    ──▶ Solutions ──▶ GameAction[]                     │
│    ──▶ {game_id}_solver_*.png (overlay)               │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│ 4. EXÉCUTION                                            │
│    GameAction[] ──▶ CoordinateSystem                    │
│    ──▶ JavaScript ──▶ Selenium clicks                  │
│    ──▶ {game_id}_actions_*.json (log)                  │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│ 5. MÉTADONNÉES                                          │
│    metadata.json ──▶ stats, temps, état final           │
└─────────────────────────────────────────────────────────┘
```

### Diagramme de Séquences - Initialisation des Services

```
Scénario ────▶ SessionSetupService.__init__()
    │                       │
    │                       ▼
    │              setup_session(difficulty)
    │                       │
    │                       ▼
    │              ┌─────────────────────┐
    │              │ NavigationService   │ ◄── auto-configuré
    │              │ ZoneCaptureService  │ ◄── auto-configuré
    │              │ OptimizedAnalysis   │ ◄── auto-configuré
    │              │ GameSolverService   │ ◄── auto-configuré
    │              │ ActionExecutor      │ ◄── auto-configuré
    │              │ GameLoopService     │ ◄── auto-configuré
    │              │ TestPatternsService │ ◄── auto-configuré
    │              └─────────────────────┘
    │
    ▼
Prêt pour exécution
```

---

## Références Croisées

- **[lib/INDEX.md](../lib/INDEX.md)** : Documentation des modules techniques
- **[docs/specs/](../docs/specs/)** : Architecture et spécifications
- **[bot_1000mines.py](../bot_1000mines.py)** : Scénarios et orchestration
