# Bibliothèque `lib/` - Index des Opérateurs

## Vue d'ensemble

Documentation complète de tous les opérateurs (méthodes, classes, constantes) disponibles dans la bibliothèque `lib/` avec descriptions détaillées.

---

## Modules sollicités par les scénarios actifs

> Les scénarios encore supportés (1 : initialisation, 2 : analyse locale, 3 : passe unique, 4 : boucle complète)
> s'appuient sur la phase partagée `Minesweeper1000Bot.run_initialization_phase()` qui orchestre les modules suivants :

| Étape | Modules lib/ impliqués | Scénarios |
|-------|------------------------|-----------|
| Setup navigateur + ancrage | `s0_interface/s00_browser_manager`, `s0_interface/controller`, `s0_interface/s03_Coordonate_system` | 1, 3, 4 |
| Déplacement + overlay combiné | `s0_interface/s03_Coordonate_system`, `s1_capture/combined_overlay` (debug uniquement) | 1, 3, 4 |
| Capture zone/viewport | `s1_capture/s11_canvas_capture` (canvas) + fallback screenshot | 1, 3, 4 |
| Analyse offline | `s2_recognition/*`, `s3_tensor/grid_state.py` | 2 |
| Analyse + résolution in-loop | `s1_capture/screenshot_manager`, `s2_recognition/*`, `s3_tensor/*`, `s4_solver/*` | 3, 4 |
| Exécution d'actions | `s0_navigation/game_controller`, `s0_navigation/coordinate_system` | 3, 4 |

Cette table sert de guide rapide pour savoir quelle partie de `lib/` vérifier en fonction du scénario exécuté.

---

## Core Bot Modules

### Coordinate System
- **path**: lib/s0_interface/s03_Coordonate_system.py
- **type**: Utilitaires mathématiques de conversion de coordonnées (architecture modulaire)
- **classes**:
  - `CoordinateConverter` - Convertisseur de coordonnées principal + expose `canvas_locator`
  - `CanvasLocator` - Découverte des tuiles canvas 512×512
  - `ViewportMapper` - Inspection des limites et viewport (partagé avec s1_capture)
- **methods (CoordinateConverter)**:
  - `__init__(cell_size, cell_border, anchor_element, driver)` - Initialise le convertisseur
  - `get_control_element()` - Récupère l'élément DOM #control
  - `setup_anchor()` - Configure l'élément anchor comme référence (#anchor)
  - `refresh_anchor()` - Rafraîchit la position de l'anchor avant conversion
  - `get_anchor_css_position()` - Récupère les coordonnées CSS réelles (getBoundingClientRect)
  - `convert_canvas_to_screen(canvas_x, canvas_y)` - Convertit Canvas vers Screen
  - `convert_screen_to_canvas(screen_x, screen_y)` - Convertit Screen vers Canvas
  - `convert_canvas_to_grid(canvas_x, canvas_y)` - Convertit Canvas vers Grid
  - `convert_screen_to_grid(screen_x, screen_y)` - Convertit Screen vers Grid
  - `convert_grid_to_canvas(grid_x, grid_y)` - Convertit Grid vers Canvas
  - `convert_grid_to_screen(grid_x, grid_y)` - Convertit Grid vers Screen
  - `grid_to_screen_centered(grid_x, grid_y)` - Centre d'une cellule en écran
- **methods (ViewportMapper)**:
  - `__init__(converter, driver)` - Initialise avec un convertisseur
  - `get_viewport_bounds()` - Calcule les bornes du viewport selon `VIEWPORT_CONFIG`
  - `get_viewport_corners()` - Calcule les 4 coins du viewport
- **dependencies**: src.config, selenium
- **constants**: CELL_SIZE, CELL_BORDER, GRID_REFERENCE_POINT, VIEWPORT_CONFIG
- **features**: Architecture modulaire, coordonnées CSS fiables (x=980, y=806), debug fenêtre, JavaScript natif

### Viewport & Game Controllers
- **path**: lib/s0_interface/controller.py, lib/s0_interface/s03_game_controller.py
- **type**: Façade viewport + navigation
- **classes**:
  - `InterfaceController` - Façade publique s0 (rafraîchit l’ancre, fournit `get_capture_meta`, lit `#status`)
  - `StatusReader` - Lecture DOM `div#status` (scores, vies, bonus_threshold)
  - `GameSessionController` - Sélection du mode de jeu et initialisation
  - `NavigationController` - Navigation et interaction souris
- **methods (InterfaceController)**:
  - `from_browser(browser)` - Compose BrowserManager + CoordinateConverter + NavigationController + StatusReader
  - `refresh_state()` - Met à jour l’état anchor/viewport
  - `ensure_visible(grid_bounds)` - Force la visibilité d’une zone grille
  - `get_capture_meta(canvas_x, canvas_y)` - Données pour `canvas.toDataURL()`
  - `read_game_status()` - Retourne un `GameStatus`
- **methods (StatusReader)**:
  - `read_status()` - Lit `#status` et construit `GameStatus` (lives, bonus_counter, thresholds)
- **methods (GameSessionController)**:
  - `__init__(driver)` - Initialise le contrôleur avec WebDriver
  - `get_difficulty_from_user()` - Interface CLI pour choisir la difficulté
  - `select_game_mode(difficulty)` - Configure le mode de jeu
  - `get_coordinate_converter()` - Retourne le convertisseur de coordonnées
  - `get_viewport_mapper()` - Retourne le mapper de viewport
- **methods (NavigationController)**:
  - `__init__(driver, converter, viewport_mapper)` - Initialise avec les composants de coordonnées
  - `move_view_js(dx, dy)` - Déplace le viewport via JavaScript natif
  - `click_cell(grid_x, grid_y, right_click)` - Clique sur une cellule (JavaScript MouseEvent)
  - `execute_game_action(action, coord_system)` - Exécute une action de jeu
  - `move_viewport(dx, dy, coord_system)` - Déplace le viewport avec coordonnées
- **dependencies**: selenium, src.config, coordinate_system
- **features**: Façade unique s0, MouseEvent avancés, lecture DOM status intégrée, logging structuré

### Browser Manager
- **path**: lib/s0_interface/s00_browser_manager.py
- **type**: Gestionnaire de session navigateur
- **methods**:
  - `__init__()` - Initialise le gestionnaire
  - `start_browser()` - Démarre Chrome WebDriver
  - `get_driver()` - Retourne l'instance WebDriver
  - `navigate_to(url)` - Navigue vers une URL
  - `wait_for_element(selector, timeout)` - Attend un élément DOM
  - `execute_javascript(script, *args)` - Exécute du JavaScript
  - `get_page_info()` - Récupère les informations de la page
  - `stop_browser()` - Arrête proprement le navigateur
- **dependencies**: selenium, src.config, typing
- **features**: Gestion automatique Chrome, timeouts configurables, cleanup

---

## Utilities Modules

### Performance Monitor
- **path**: lib/performance_monitor.py
- **type**: Moniteur de performance système
- **methods**:
  - `__init__(log_interval)` - Initialise le monitoring
  - `start_monitoring()` - Démarre la surveillance
  - `stop_monitoring()` - Arrête la surveillance
  - `record_metric(name, value, unit, context)` - Enregistre une métrique
  - `measure_function_performance(func_name)` - Décorateur de performance
  - `get_current_metrics()` - Retourne les métriques actuelles
  - `get_performance_monitor()` - Singleton du moniteur
  - `measure_performance(func_name)` - Décorateur global
- **dependencies**: psutil, threading, dataclasses
- **features**: Monitoring CPU/RAM, détection anomalies, rapports automatiques

### Configuration Manager
- **path**: config.py
- **type**: Configuration centralisée (constantes uniquement)
- **constants**:
  - `CELL_SIZE` - Taille des cellules en pixels
  - `CELL_BORDER` - Taille des bordures
  - `DIFFICULTY_CONFIG` - Configurations des difficultés
  - `DEFAULT_DIFFICULTY` - Difficulté par défaut
  - `VIEWPORT_CONFIG` - Configuration du viewport
- **dependencies**: None
- **validation**: Paramètres validés au démarrage

---

## Vision System Modules

### Canvas Capture & Composite
- **paths**: 
  - `lib/s1_capture/s11_canvas_capture.py`
  - `lib/s1_capture/s12_canvas_compositor.py`
- **type**: Capture canvas directe, fallback fenêtre complète et composition alignée.
- **responsabilités**:
  - `s11_canvas_capture` : conversion `canvas.toDataURL`, captures partielles/viewport, helpers `_grid_bounds_to_pixels`, fallback screenshot.
  - `s12_canvas_compositor` : assemblage multi-canvases, alignement strict sur les cellules (`cell_ref`, `ceil/floor`), recadrage, recalcul `grid_bounds`, sauvegarde `full_grid_*.png`.
- **features**: API stable, génération `temp/games/{id}/s1_raw_canvases`, validations stride (asserts), dérivé par `ZoneCaptureService.compose_from_canvas_tiles`.

### Interface Detector (legacy)
- **path**: lib/s1_capture/interface_detector.py
- **type**: Détecteur d'éléments d'interface (legacy – sera retiré après migration ScoreReader)
- **methods**:
  - `__init__(driver)` - Initialise avec WebDriver
  - `detect_interface_positions()` - Détecte les positions des éléments UI
  - `get_interface_config()` - Retourne la configuration UI
  - `create_interface_mask(image_shape)` - Crée un masque pour l'interface
  - `create_annotated_screenshot(screenshot_path)` - Ajoute des annotations
- **dependencies**: PIL, selenium, typing
- **features**: Détection automatique escape_link, status, controls

---

## Vision Recognition Modules (s2_vision / s2_recognition)

### Center Template Matcher (s2_vision)
- **path**: lib/s2_vision/s21_template_matcher.py
- **type**: Matching déterministe zone 10×10 (marge 7 px) basé sur les artefacts `s21_templates_analyzer`.
- **classes**:
  - `CenterTemplateMatcher` – charge `central_templates_manifest.json` et expose `classify_cell` / `classify_grid`.
  - `MatchResult` – contient `symbol`, `distance`, `threshold`, `confidence`, `distances`, `margin`.
- **caractéristiques**:
  - Heuristiques uniformes (`UNIFORM_THRESHOLDS["unrevealed"]=200`, `["empty"]=25`, `["question_mark"]=200`).
  - Discriminant pixel pour distinguer `exploded` / `unrevealed` avec marge 9 px.
  - Ordre de priorité fixe (`unrevealed → exploded → flag → number_1..8 → empty → question_mark`) avec early exit, décor testé en dernier recours.
  - Génère des overlays de debug quand nécessaire (voir `s22_vision_overlay`).
  - Tests de référence : `python tests/test_s2_vision_performance.py` (<0,6 s/screenshot sur machine de ref).

### Vision Overlay
- **path**: lib/s2_vision/s22_vision_overlay.py
- **type**: Générateur d’overlay runtime pour visualiser `MatchResult`.
- **caractéristiques**:
  - Couleurs explicites (question_mark = blanc comme unrevealed, decor = gris/noir).
  - Label + pourcentage affichés en 2 lignes compactes (font 11, espacement minimal).
  - Utilisé dans les tests et pour l’audit manuel des captures.

### Templates Analyzer
- **path**: lib/s2_vision/s21_templates_analyzer/*
- **type**: Outils de génération d’artefacts (variance + templates centraux).
- **scripts**:
  - `variance_analyzer.py` – heatmaps & validation marge 7 px.
  - `template_aggregator.py` – extraction zone 10×10, calcul mean/std, génération `central_templates_manifest.json`.
- **artefacts**:
  - `template_artifact/<symbol>/mean_template.npy`, `std_template.npy`, `preview.png`.
  - `central_templates_manifest.json` – index officiel chargé par le matcher.

> Les anciens modules `lib/s2_recognition/*` (FixedTemplateMatcher, mapper, legacy color recognizers) restent documentés ci-dessous pour référence historique. Le pipeline actif repose sur `lib/s2_vision`.

### Fixed Template Matcher (legacy)
- **path**: lib/s2_recognition/template_matching_fixed.py
- **type**: Reconnaissance hybride par corrélation/différence
- **responsabilités**:
  - Chargement des templates `s21_templates/symbols`
  - `recognize_grid(image_path, zone_bounds)` - Retourne (symbol, confidence) par cellule
  - `match_cell_hybrid(cell_image)` - Sélectionne dynamiquement la meilleure méthode de matching
- **dependencies**: numpy, PIL, src.lib.s3_tensor.types
- **features**: Support des zones absolues, statistiques rapides (>3500 cellules/2s)

### Vision → Game Mapper
- **path**: lib/s2_recognition/mapper.py
- **type**: Conversion des types Vision ↔ Game
- **methods**:
  - `map_cell_type(cell_type)` - CellType → CellSymbol
  - `map_symbol(cell_symbol)` - CellSymbol → CellType
- **dependencies**: lib.s3_tensor.cell, lib.s2_recognition.types
- **features**: Gestion des types inconnus, conversions bidirectionnelles

### Legacy Color Recognizers
- **path**: lib/recognition/*
- **note**: Conservés pour référence historique (analyse couleur brute) mais non utilisés dans le pipeline principal depuis la migration vers s2_recognition.
- **type**: Reconnaissance de cellules par couleurs
- **methods**:
  - `extract_dominant_colors(image, k)` - Extrait les couleurs dominantes
  - `__init__()` - Initialise le reconnaisseur
  - `recognize_single_cell(cell_image, coordinates)` - Reconnaît une cellule
  - `recognize_grid_batch(grid_image, grid_bounds)` - Reconnaît une grille complète
  - `recognize_multiple_cells(cells_images)` - Reconnaît plusieurs cellules
- **dependencies**: PIL, sklearn.cluster, typing
- **features**: K-means clustering, analyse couleurs, confiance

### Cell Classifier
- **path**: lib/recognition/cell_classifier.py
- **type**: Classification intelligente de cellules
- **methods**:
  - `classify_cell(colors, image)` - Classifie une cellule
  - `classify_cell_by_colored_pixels(colors)` - Classification par pixels colorés
  - `classify_by_direct_analysis(image)` - Analyse directe de l'image
  - `get_confidence_score(predicted_type, colors)` - Calcule la confiance
  - `extract_cells_from_grid(grid_image, ...)` - Extrait les cellules d'une grille
  - `analyze_grid_structure(grid_image)` - Analyse la structure de la grille
- **dependencies**: PIL, numpy, typing
- **features**: Multi-algorithmes, scoring de confiance, analyse structurelle

### Overlay Generator
- **path**: lib/recognition/overlay_generator.py
- **type**: Générateur d'overlays visuels
- **methods**:
  - `__init__(cell_size, output_dir)` - Initialise avec taille et dossier
  - `generate_recognition_overlay(grid_image, grid_analysis)` - Overlay de reconnaissance
  - `generate_confidence_overlay(grid_image, grid_analysis)` - Overlay de confiance
  - `generate_comparison_overlay(original_image, ...)` - Overlay comparatif
  - `generate_analysis_report(grid_analysis)` - Rapport d'analyse
  - `get_recent_overlays(limit)` - Liste les overlays récents
- **dependencies**: PIL, typing, pathlib, json
- **features**: Overlays multi-types, rapports JSON, gestion historique

### Types
- **path**: lib/recognition/types.py
- **type**: Définitions de types de données
- **classes**:
  - `ColorInfo` - Information sur une couleur (rgb, hex, proportion)
  - `CellAnalysis` - Analyse complète d'une cellule
  - `GridAnalysis` - Analyse complète d'une grille
- **methods**:
  - `CellAnalysis.get_cell_count()` - Nombre de cellules
  - `CellAnalysis.get_cells_by_type(type)` - Filtre par type
  - `CellAnalysis.get_mine_positions()` - Positions des mines
  - `CellAnalysis.get_summary()` - Résumé statistique
- **dependencies**: dataclasses, typing, enum
- **features**: Types structurés, méthodes utilitaires

---

## Game State Modules (s3_tensor)

### Cell
- **path**: lib/s3_tensor/cell.py
- **type**: Définition des cellules et états
- **classes**:
  - `CellSymbol` - Enum des symboles (UNKNOWN, UNREVEALED, EMPTY, FLAG, MINE, NUMBER_1-8)
  - `ProcessingStatus` - Enum des statuts (NONE, TO_PROCESS, PROCESSED)
  - `Cell` - Dataclass représentant une cellule
- **properties**:
  - `is_number` - Vérifie si la cellule contient un chiffre
  - `number_value` - Retourne la valeur numérique si applicable
- **dependencies**: dataclasses, enum, datetime
- **features**: Gestion automatique des timestamps, propriétés calculées

- **path**: lib/s3_tensor/grid_state.py
- **type**: Base de données d'état du jeu
- **methods**:
  - `__init__()` - Initialise la base de données
  - `get_cell(x, y)` - Récupère ou crée une cellule
  - `update_cell(x, y, symbol, confidence)` - Met à jour l'état d'une cellule
  - `mark_as_processed(x, y)` - Marque une cellule comme traitée
  - `get_cells_to_process()` - Retourne les cellules à traiter
  - `get_known_cells_count()` - Compte les cellules connues
  - `get_summary()` - Résumé statistique de l'état
- **dependencies**: typing, datetime, lib.game.cell
- **features**: Gestion automatique du ProcessingStatus, calcul des bounds, persistance mémoire

- **path**: lib/s3_tensor/mapper.py
- **type**: Convertisseur entre types Vision et Game
- **methods**:
  - `map_cell_type(vision_type)` - Convertit CellType vers CellSymbol
  - `map_symbol(game_symbol)` - Convertit CellSymbol vers CellType
- **dependencies**: lib.recognition.types, lib.game.cell
- **features**: Mapping bidirectionnel, gestion des types inconnus

---

---

## Guide d'Utilisation Rapide

### Conversions & Navigation
Utiliser **lib/s0_navigation/** (Coordinate System + NavigationController + BrowserManager). Les coordonnées CSS reposent sur `#anchor` avec `getBoundingClientRect()` et les déplacements s'appuient sur du JavaScript natif.

### Capture & Interface
Utiliser **lib/s1_capture/** pour les captures viewport/zone, la détection interface et la génération d'overlay combiné (interface + grille).

### Reconnaissance
Utiliser **lib/s2_recognition/** (FixedTemplateMatcher + mapper) pour remplir `grid_state_db.json` à partir des screenshots avec les coordonnées absolues fournies par la capture.

### État & Résolution
Utiliser **lib/s3_tensor/** pour la persistance (`GridDB`, `GamePersistence`, `CellSymbol`) et **lib/s4_solver/** pour les overlays solver/segmentation et les composants CSP.

### Monitoring
**Performance Monitor** reste disponible pour suivre CPU/RAM et instrumenter les services.

---

*Dernière mise à jour : 8 Décembre 2025 – migration s0_navigation / s1_capture / s2_recognition / s3_tensor / s4_solver*
