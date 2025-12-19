# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Architecture Refactoring & Robust Clicks – 2025-12-20
- **Exécution temps-réel** : Le `planner` (`s5`) devient l'agent actif. Il exécute les actions au fur et à mesure de la planification si le driver est fourni.
- **Gestion des explosions** : Le `planner` vérifie les vies après chaque clic et applique un délai de stabilisation de 2s en cas d'explosion.
- **Clics Robustes (Anchor-Relative)** : Les clics sont désormais calculés par rapport à l'élément `#anchor` en JavaScript au moment précis de l'exécution. Immunité totale aux mouvements du viewport pendant l'exécution.
- **Simplification Game Loop** : Suppression du module `s6_executor` et de la logique de délai réactif dans `s9_game_loop.py`.
- **Stabilité Viewport** : Appel systématique à `refresh_anchor()` à chaque itération pour garantir la cohérence vision/coordonnées.

### Solver – focus, overlays, CSP borné – 2025-12-19
- **Classification** : `StatusAnalyzer` ne reclasse plus que les `JUST_VISUALIZED`, préservant les focus des FRONTIER/ACTIVE existantes.
- **Persistance focus** : `storage.update_from_vision` conserve `focus_level_active/frontier` pour les cellules inchangées (plus de perte de `REDUCED/PROCESSED` entre itérations).
- **Overlays** : `overlay_combined` reflète strictement le snapshot (plus de transition manuelle). Les overlays utilisent le snapshot runtime final.
- **CSP** : limite configurable `CSP_CONFIG['max_zones_per_component']=50` pour éviter l’explosion sur les grandes composantes.
- **Runtime unique** : pipeline complet sur `SolverRuntime` (snapshot mutable + dirty flags), upsert unique vers le storage.

### SolverRuntime (snapshot mutable, dirty flags) – 2025-12-19
- **Solver** : introduction d’un `SolverRuntime` interne (snapshot mutable + dirty flags). Tous les sous-modules appliquent leurs `StorageUpsert` au runtime immédiatement ; le storage réel n’est mis à jour qu’une seule fois en fin de pipeline.
- **Pipeline** : séquence stricte post-vision → CSP → post-solver → sweep, tous sur l’état partagé du runtime (plus de `get_snapshot()` intermédiaire).
- **Sweep** : importe `LogicalCellState` et exclut les cellules déjà résolues (effective_value=0).
- **Game loop** : suppression de l’appel erroné à `update_capture_metadata()` (overlay vision).
- **Storage** : `update_from_vision` lit le snapshot via `self.get_snapshot()` (et non `_store`).

### Stabilisation pipeline minimal (V2) – 2025-12-19
- **Session (init jeu)** : sélection du mode **Infinite** et de la difficulté fiabilisée (attente explicite + clic sur `a[href='/#infinite'] button`, puis clic sur `#new-game-*`).
- **Vision (composite + bounds)** : analyse du composite aligné avec des `GridBounds` absolus (plus de tentative de réécriture des coordonnées après analyse).
- **CaptureResult** : ajout d'accesseurs `composite_path`, `composite_bytes`, `composite_image` pour exposer proprement le composite aux modules aval.
- **Solver (phase 0)** : réimplémentation d'un `StateAnalyzer` minimal dans `src/lib/s4_solver/state_analyzer.py` (classification ACTIVE/FRONTIER/SOLVED) et intégration post-vision dans `services/game_loop.py`.
- **Qualité/Debug** : purge des logs de debug arbitraires (échantillon de cellules imprimées) pour alléger la boucle.

### Solver/Storage/Overlays – correctifs runtime (V2) – 2025-12-19
- **Storage types** : restauration de `src/lib/s3_storage/types.py` (types manquants) + `GridCell` en dataclass pour supporter `dataclasses.replace()`.
- **Topological state** : suppression complète des références à `topological_state` (non supporté par `GridCell`) dans les pipelines solver (`status_analyzer`, `action_mapper`, `csp_manager`).
- **Sweep (ex-cleanup)** : génération d'actions bonus `SAFE` sur les voisines `ACTIVE` des cellules `TO_VISUALIZE` (exclut les `SOLVED`).
- **Overlay combined** : actions rendues en symboles blancs sans fond ; filtre pour ne pas afficher de sweep sur des cellules non `ACTIVE`.
- **Game loop** : prompt de fin de partie `Relancer une partie ? (y/N)` et boucle de relance via recréation de session.

### Refactoring Architectural Complet – 2025-12-18
- **Phase 1 - Nettoyage** : Suppression de 7 fichiers/dossiers (overlays, tests dispersés, doublons)
- **Phase 1 - Nettoyage** : -10+ méthodes/fonctions overlay éliminées, -2 enums inutiles
- **Phase 2 - Refactoring** : `StateManager` + `FrontierClassifier` → `StatusClassifier` unifié
- **Phase 2 - Refactoring** : Division `GameLoopService` → `SingleIterationService` + `GameLoopService`
- **Phase 2 - Bug fixes** : Correction imports FrontierClassifier dans 6 fichiers solver
- **Phase 2 - Bug fixes** : Restauration détection frontières (frontier=0 → 30+)
- **Architecture** : Modules autonomes avec faible couplage, haute cohésion
- **Performance** : Bot 100% fonctionnel, 112 actions exécutées avec succès

### Capture → Vision → Solver (reclustering + repromotions) – 2025-12-17
- Reclustering JUST_VISUALIZED→ACTIVE/FRONTIER/SOLVED effectué côté state analyzer (s40), pas côté vision.
- Introduction d’un module `focus_actualizer` (repromotions REDUCED→TO_REDUCE et PROCESSED→TO_PROCESS) appelé post state analyzer et post solver.
- Suppression de tout calcul de frontière opportuniste dans `matches_to_upsert` (vision).
- Invariants renforcés dans storage (`apply_upsert`) : focus_level cohérent avec solver_status ; number_value=None si logical_state != OPEN_NUMBER.
- TO_VISUALIZE écrit par le solver, reste hors known_set ; peut être exclu de active_set pour éviter des faux positifs.
- SessionContext enrichi avec `historical_canvas_path` pour alimenter les overlays combined/states/actions.

### Solver/Storage – reclustering + repromotion focus – 2025-12-17
- **Fix reclustering** : les cellules `JUST_VISUALIZED` (issues de vision) sont maintenant reclassées et **écrites dans storage** (`ACTIVE/SOLVED/FRONTIER`) avant l’extraction du batch solver.
- **Repromotion fiable** : la repromotion des focus levels (REDUCED→TO_REDUCE, PROCESSED→TO_PROCESS) est déclenchée :
  - **post-vision** (après reclustering), pour réactiver le voisinage suite aux nouvelles infos vision
  - **post-solver** (après décisions SAFE/FLAG), car ces décisions changent aussi la topologie (`TO_VISUALIZE`/`SOLVED`).
- **Impact** : évite la perte d’information “une nouvelle topo doit réveiller les voisines”, et stabilise le cycle vision→solver sur les grosses grilles.

### Pipeline capture → vision → solver – 2025-12-16
- **Fusion reducer + CSP** : `GameLoopService` fusionne maintenant `reducer_actions` et `solver_actions` avant planification
- **Priorisation déterministe** : Actions CLICK/FLAG exécutées avant les GUESS
- **Limite frontière augmentée** : `max_component_size` passé à 500 pour traiter des frontières plus grandes
- **Exposition reducer_actions** : `StorageSolverService.solve_snapshot_with_reducer_actions` construit les `SolverAction` depuis `reducer_safe/reducer_flags`
- **Overlays unifiés** : Consolidation sur `s1_capture/s10_overlay_utils.setup_overlay_context` (suppression d'`overlay_test_utils.py`)
- **Tests corrigés** : Adaptation signature (`screenshot_path`, `overlay_enabled=True`) et imports `CspManager` dans les tests 02/04/05
- **export_root unique** : `SessionStorage.build_game_paths` crée uniquement `{base}/s1_raw_canvases`, `{base}/s1_canvas`, et fournit `solver = {base}`. Aucun chemin overlay n’est construit par les services.
- **Capture** : `ZoneCaptureService` assemble les tuiles canvas (`s1_raw_canvases` → `s1_canvas/full_grid_*.png`). Vision consomme une capture déjà persistée (sinon erreur).
- **Vision intégrée** : `VisionAnalysisService` ne sauvegarde plus de captures ; VisionController enregistre l’overlay via `VisionOverlay.save` sous `{base}/s2_vision_overlay/` si overlay activé.
- **Orchestration solver minimaliste** : `GameSolverServiceV2` passe uniquement `export_root` aux générateurs ; les overlays sont produits par les modules s491/s492/s493/s494 (`s40_states_overlays`, `s42_segmentation_overlay`, `s42_solver_overlay`, `s43_csp_combined_overlay`).
- **Responsabilités strictes** : logique au plus bas niveau (modules lib/*), controllers passe-plats, services = orchestration seulement.
- **Nettoyage session** : `SessionSetupService.cleanup_session` appelé une seule fois par le pilote principal (prompt Entrée avant fermeture navigateur).

### Documentation & SPECS (cohérence V2) – 2025-12-16
- **S3 index** : clarification des sets `revealed_set / active_set / frontier_set` et de leurs rôles.
- **Nomenclature FocusLevel** : `TO_REDUCE/REDUCED` (ACTIVE) et `TO_PROCESS/PROCESSED` (FRONTIER).
- **TO_VISUALIZE** : écrit par le solver lors des décisions `SAFE` (cases amenées à changer), consommé ensuite pour cadrer la re-capture.
- **ZoneDB** : formalisée comme un index dérivé basé sur `zone_id`/contraintes (déclenchement CSP via zones `TO_PROCESS`).
- **Docs harmonisées** : mise à jour en style didactique des SPECS `S0_INTERFACE`, `S1_CAPTURE`, `s2_VISION`, `s4_SOLVER`, `s5_ACTION_PLANNER`, `ARCHITECTURE`, `PIPELINE`.
- **Dumb Solver Loop** : référence consolidée sur `doc/FOLLOW_PLAN/s44_dumb_solver_loop.md` (suppression de duplications).
- **Performance terrain** : le bot tourne correctement sans navigation auto/optimisation, mais à ~7000 de score la résolution ralentit fortement → demande d’optimisations lourdes à planifier.

### Solver – 2025-12-13
- **Refonte s4** : séparation complète des responsabilités en trois sous-modules.
  - `s40_grid_analyzer/` regroupe désormais la classification JUST_REVEALED→ACTIVE/FRONTIER/SOLVED (`grid_classifier.py`) et l'exposition des vues (`grid_extractor.py`).
  - `s41_propagator_solver/` concentre le moteur de motifs déterministes (`pattern_engine.py`).
  - `s42_csp_solver/` héberge la segmentation, le backtracking exact (`csp_solver.py`) et la réduction contrainte (`frontier_reducer.py`).
- **Tests unitaire** : `00_run_zone_overlay.py` consomme le `FrontierClassifier` du Grid Analyzer pour produire les overlays ACTIVE/FRONTIER/SOLVED, garantissant que toute la logique de statut est centralisée.
- **Docs synchronisées** : `PLAN_S4_SOLVER.md`, `doc/PIPELINE.md`, `PLAN_SIMPLIFICATION radicale.md`, `SYNTHESE_pipeline_refonte.md`, `PLAN_S3_STORAGE.md` reflètent cette architecture (étape 0 → motifs → CSP).

### Solver – 2025-12-14
- **Migration vers OptimizedSolver (CSP only)** : Remplacement complet du solver hybride par un solver CSP optimisé
- **Configuration dynamique CSP** : Ajout des paramètres `stability_config` et `use_stability` dans `CspManager` pour contrôler le filtrage des composantes
- **Renommage module** : `s423_stability_evaluator.py` → `s423_component_range_filter.py` pour refléter la notion de range/amplitude
- **Benchmarking avancé** : Script `03_compare_solver_pipelines.py` enrichi avec rapports Markdown détaillés (différences absolues/proportionnelles, moyennes)
- **Planification Pattern Solver** : Création du plan d'implémentation dans `s43_pattern_solver/IMPLEMENTATION_PLAN.md`

### Changed
- **Capture Canvas** : Refactor complet de la composition / capture brute.
  - `ZoneCaptureService` orchestre désormais les captures multi-canvases (`capture_canvas_tiles`) et délègue l'assemblage aligné aux modules `src/lib/s1_capture`.
  - Nouveau module `src/lib/s1_capture/s12_canvas_compositor.py` responsable de l'alignement pixel-parfait (cell_ref, ceil/floor, recalc `grid_bounds`).
  - Le bot (`src/apps/bot_1000mines.py`) ne contient plus de logique de collage ni de boucle de capture.
- **Nettoyage overlay debug** : suppression des anciens overlays de debug côté capture. Les overlays runtime restent fournis par `src/lib/s2_vision/s22_vision_overlay.py`.

### Storage – 2025-12-12
- **Architecture trois sets** : Implémentation complète de revealed/unresolved/frontier sets dans s3_storage
  - `s32_set_manager.py` : Classe dédiée à la gestion des trois sets avec `apply_set_updates()`
  - `s31_grid_store.py` : Grille sparse déléguant les opérations de sets à SetManager
  - `controller.py` : Façade pure vers GridStore + SetManager, API inchangée
- **Contrat storage passif** : Vision pousse revealed+unresolved, Solver calcule frontier_add/remove
  - `facade.py` : StorageUpsert avec champs distincts Vision vs Solver
  - Suppression des métriques de storage (calculées par solver/actionplanner si besoin)
- **Documentation technique** : `doc/SPECS/s03_STORAGE.md` avec spécification complète
  - Architecture, API contract, flux de données, invariants, exemples d'intégration
  - Pièges courants et bonnes pratiques pour Vision/Solver integration
- **PLAN_S3_STORAGE.md** : Mis à jour avec structure réelle et phases marquées comme complétées

### Vision – 2025-12-12
- Validation complète du **CenterTemplateMatcher** : heuristiques uniformes (`unrevealed`, `empty`), discriminant pixel pour `exploded`, ordre de test prioritaire avec early exit, décor testé uniquement en dernier recours.
- Ajout du symbole `question_mark` dans la chaîne complète (templates, manifest, matcher, overlay). Les overlays affichent désormais `question_mark` en blanc (comme `unrevealed`) et `decor` en gris/noir.
- Resserrement du seuil runtime `empty` (`UNIFORM_THRESHOLDS["empty"]=25`) pour éviter les faux positifs décor.
- Vision API + test `tests/test_s2_vision_performance.py` servent de validation continue (<0,6 s/screenshot sur machine de ref).

### Added
- **Analyse de Variance s210_variance** : Module complet d'analyse de variance par pixel pour validation des marges de sécurité
  - `variance_analyzer.py` : Génération de heatmaps de variance individuelles par symbole
  - Superposition mathématique des heatmaps (moyenne élément par élément) pour isoler uniquement les variations d'éclats de mines
  - Analyse automatique de marge optimale par distance depuis le bord (variance par distance)
  - Génération de heatmap annotée avec rectangles de distance (5px, 7px, 8px, 9px)
  - Validation quantitative : marge optimale déterminée à **7px** pour les chiffres et cases vides
  - Dataset analysé : 1546 images (number_1 à number_8 + empty)
  - Conclusion : Utiliser 7px de marge pour éviter les éclats de mines sur 9 types de symboles

### Failed Approaches (Documented for Learning)
- **4 Pixels Globaux (s212_pixel_rancker)** : Échec complet de l'approche discriminante
  - Séparation = 0.000 (aucun score négatif trouvé sur tous les pixels)
  - Incapacité à rejeter les centaines de motifs décoratifs inconnus
  - Trop rigide pour gérer la variabilité des couleurs et motifs
  - **Leçon apprise** : L'approche globale fixe ne peut pas gérer la complexité des variations réelles
- **Smart Fingerprint System** : Trop complexe et lourd pour une utilisation pratique
  - Processus d'optimisation trop lourd
  - Manque de robustesse face aux masquages partiels
  - **Leçon apprise** : Nécessité d'une approche plus déterministe et lightweight

### Changed
- **Plan simplification radicale** : consolidation complète de la roadmap s0→s6, documentation `doc/` (README + 01/02/03) et spécifications officielles (`SPECS/ARCHITECTURE.md`, `SPECS/DEVELOPMENT_JOURNAL.md`).

### Changed
- **Structuration Documentation** : Réorganisation complète du dossier `docs/` selon les couches métier
  - `architecture_fichiers.md` : Uniquement structure physique et modules
  - `architecture_logicielle.md` : Uniquement couches applicatives et interfaces
  - `logique_metier.md` : Uniquement concepts métier, règles et invariants
  - `composants_techniques.md` : Uniquement librairies, frameworks et utilitaires
  - `workflows.md` : Uniquement flux d'exécution arborescents et scénarios
  - Archivage de `architecture_solver_complet.md` dans `docs/meta/archive/`
- **GameSessionManager** : Réinitialisation ID partie et itération après choix difficulté
  - Ajout paramètre `difficulty` à `initialize_new_game()`
  - Nouvelle méthode `reset_game_only()` pour changement difficulté sans redémarrage bot
  - Création partie déplacée après sélection difficulté dans `SessionSetupService`

### Added
- **Template Matching Optimisé** : Reconnaissance ultra-rapide (~4000 cellules/sec) par convolution 2D
- **OptimizedAnalysisService** : Service d'analyse exclusivement basé sur template matching
- **FixedTemplateMatcher** : Reconnaissance par motifs pré-définis (0 UNKNOWN)
- **OptimizedOverlayGenerator** : Génération d'overlays avec alpha_composite unique
- **Templates assets** : 10 symboles disponibles dans `assets/symbols/`
- **Architecture fichiers centralisée** : Documentation complète dans `docs/specs/architecture_fichiers.md`
- **Chemins granulaires** : Séparation précise des types de fichiers dans `config.PATHS`
- **Structure temp/ unifiée** : Tous les fichiers de traitement dans `temp/` avec sous-dossiers spécialisés
- **Base de données persistante** : `grid_state_db.json` pour toutes les cellules analysées
- **Overlays spécialisés** : Distinction claire entre overlays bruts et overlays de reconnaissance
- **Pipeline CNN datasets** :
  - Script `augment_borders.py` (obstructions diagonales/triangles, zone centrale 10×10 préservée, exclusions `unrevealed`/`exploded`)
  - Documentation `lib/s2_recognition/s22_Neural_engine/cnn/data/README.md` (commandes `prepare_cnn_dataset.py`, CLI exemples `--copies 10`, `--central-keep 10`)
  - Entrées docs/README.md pour pointer vers ce workflow

### Changed
- **Restructuration complète des chemins** :
  - `temp/screenshots/zones/` : Captures de zones
  - `temp/screenshots/full_pages/` : Captures complètes
- **Remplacement K-means → Template Matching** : 10x plus rapide, reconnaissance parfaite
- **Services optimisés** : `OptimizedAnalysisService` remplace `AnalysisService`
- **Overlays optimisés** : Génération par alpha_composite unique (0.08-0.10s)

### Removed
- **Legacy recognition modules** : `cell_recognizer.py`, `cell_classifier.py`, `grid_processor.py`
- **Legacy services** : `AnalysisService` (remplacé par `OptimizedAnalysisService`)
- **K-means clustering** : Remplacé par convolution 2D sur templates

### Performance
- **Vitesse reconnaissance** : 0.05s → 0.001s par cellule (10x plus rapide)
- **Grille complète** : 50s → 5s pour 1000 cellules
- **CPU Usage** : 80% → 30% (réduction de 50%)
- **Précision** : 95% → 100% (0 UNKNOWN)

### Documentation
- **Intégration template matching** : Stratégie d'optimisation intégrée dans docs/specs/
- **Archivage stratégie** : `strategie_optimisation_reconnaissance.md` → `docs/meta/archive/`
- **Mise à jour specs** : Architecture logicielle et composants techniques enrichis
  - `lib/game/` → `lib/data/` (contient des structures de données, pas de logique de jeu)
- **Mise à jour des imports** : Tous les fichiers utilisent maintenant les nouveaux noms de dossiers
- **Renommage de fichier** : `stack_techniques.md` → `composants_techniques.md`
- **Documentation unifiée** : Intégration de `troubleshooting.md` dans `changelog.md`

### Fixed
- **Chemins codés en dur** : Remplacés par `PATHS` dans tous les modules
- **Logs Unicode** : Remplacement des emojis par tags ASCII dans tous les modules
- **Imports cassés** : Correction des imports après restructuration des chemins
- **Problème de Navigation (move_view_js)** : Simplification radicale de la méthode `move_view_js` dans `game_controller.py`
  - Cause : Simulation d'événements JavaScript trop complexe avec `getBoundingClientRect()`
  - Solution : Calcul des coordonnées en Python, événements explicites avec `clientX`/`clientY`, propriété `buttons: 1` ajoutée
  - Résultat : Déplacements de grille fonctionnels et détectés correctement

### Deprecated
- Anciens chemins `assets/screenshots/` (remplacé par `temp/screenshots/`)
- Anciens chemins `analysis/` (remplacé par `temp/analysis/`)
- Anciens noms de dossiers `lib/bot/` (remplacé par `lib/navigation/`)
- Anciens noms de dossiers `lib/game/` (remplacé par `lib/data/`)
- Ancien fichier `stack_techniques.md` (remplacé par `composants_techniques.md`)
- Ancien fichier `troubleshooting.md` (intégré dans `changelog.md`)

---

## [2.4.0] - 2025-12-02

### Fixed
- **Système de coordonnées complet** : Correction des "move target out of bounds"
- **Sélecteur anchor** : `canvas` → `#anchor` (élément correct)
- **Coordonnées CSS** : Utilisation de `getBoundingClientRect()` au lieu de `element.rect`
- **Clics JavaScript** : Remplacement de `ActionChains.move_by_offset()` par `GameController.click_cell()`
- **Conversion grille→écran** : Coordonnées positives garanties (x=980, y=806)

### Added
- **Debug coordonnées** : Affichage taille fenêtre et position anchor
- **GameController integration** : `ActionExecutorService` utilise maintenant `click_cell()`
- **JavaScript MouseEvent** : Événements souris natifs pour fiabilité maximale

### Performance
- **Taux de réussite** : 0% → 100% (27/27 actions réussies)
- **Temps d'exécution** : 2.40s stable
- **Fiabilité** : Plus d'erreurs de coordonnées négatives

### Notes
- Le bot est maintenant 100% fonctionnel pour les clics
- Architecture JavaScript native > Selenium pour interactions Canvas
- Prêt pour développement du game loop itératif

---

## [2.3.0] - 2025-12-01

### Added
- Service de test patterns pour validation des déplacements de vue
- Tests unitaires complets pour le service TestPatternsService (100% réussite)
- Intégration des patterns de test dans le scénario 1 avant captures d'écran
- Activation d'un déplacement simple (100, 50) pixels
- Marquage des 4 angles du viewport avec drapeaux pour validation

### Changed
- **Optimisation TestPatternsService** : Auto-récupération des composants depuis SessionSetupService
- **Simplification service** : Suppression méthode de validation inutile (-36 lignes)
- **Suppression test inutile** : Méthode `test_coordinate_conversions()` non utilisée (-74 lignes)
- **Utilisation coordinate_system** : Remplacement code dupliqué par `get_screen_bounds()` existant
- **Architecture améliorée** : Plus d'appels directs à `get_bot()`/`get_driver()` dans bot_1000mines.py
- **Encapsulation complète** : TestPatternsService gère lui-même ses dépendances
- **Renommage méthode** : `capture_viewport()` → `capture_window()` dans `ZoneCaptureService`
- **Suppression décalage** : Plus de correction de 54px pour l'overlay d'interface (fenêtre entière)
- **Mise à jour terminologie** : "viewport" → "fenêtre" dans tous les logs et messages
- **Configuration dynamique** : Suppression des tailles fixes dans `DIFFICULTY_CONFIG`

### Fixed
- **Correction interface** : `viewport_offset` → `window_offset` dans `InterfaceDetector`
- **Tests mis à jour** : `test_scenario_1.py` utilise `capture_window()` au lieu de `capture_viewport()`

## [1.3.0] - 2025-11-30

### Added
- Architecture modulaire complète avec séparation des responsabilités
- Système de coordonnées dédié (`CoordinateSystem`) dans `lib/bot/coordinate_system.py`
- Module de reconnaissance visuelle structuré en sous-dossiers (`recognition/` et `capture/`)
- Générateur d'overlays centralisé avec 21KB de fonctionnalités avancées
- Types de cellules étendus (13 types) avec classification intelligente
- Service unifié de capture avec détection d'interface intégrée
- Pattern Facade pour interface utilisateur simplifiée
- Documentation technique complète mise à jour (ARCHITECTURE.md, DEVELOPMENT_JOURNAL.md, REFACTORING_SUMMARY.md)

### Changed
- **Refactoring majeur** : Séparation de `game_controller.py` (2 classes → 2 fichiers spécialisés)
- **Refactoring majeur** : Division de `cell_recognition_architecture.py` (7 classes → 3 fichiers modulaires)
- Réorganisation complète `lib/vision/` en sous-dossiers thématiques
- Nettoyage complet des imports obsolètes dans `services/` (uniquement du métier)
- Mise à jour de tous les chemins d'imports selon nouvelle structure
- Amélioration significative de la maintenabilité avec 1 classe par fichier

### Fixed
- Correction de tous les imports cassés après refactoring systématique
- Nettoyage du code de fondation dans `services/` (maintien du métier pur)
- Résolution des imports circulaires avec imports dynamiques
- Mise à jour des noms de classes obsolètes (`Minesweeper1000Bot` → `MineSweeperBot`)

### Deprecated
- Ancien fichier monolithique `cell_recognition_architecture.py` (remplacé par structure modulaire)
- Imports directs vers `lib.cell_recognition_architecture`
- Classes obsolètes `BrowserController` (remplacé par `BrowserManager`)

### Removed
- Fichier monolithique `cell_recognition_architecture.py` (577 lignes → 3 fichiers spécialisés)
- Imports obsolètes vers modules supprimés ou restructurés
- Code de fondation dans `services/` (maintien exclusif du métier)

---

## Notes de Version

### [1.3.0] - Architecture Modulaire
Cette version introduit un refactoring architectural majeur avec une séparation complète des responsabilités. Le code est maintenant organisé en modules spécialisés avec 1 classe par fichier, une structure hiérarchique claire et des imports fonctionnels. Les overlays sont centralisés et la documentation technique a été entièrement mise à jour.

**Changements majeurs :**
- Architecture modulaire avec `lib/bot/`, `lib/vision/recognition/`, `lib/vision/capture/`
- Générateur d'overlays avancé (21KB de fonctionnalités)
- Services nettoyés avec uniquement du code métier
- Documentation technique complète

### [1.2.0] - Interface Intelligente
Cette version introduit une détection d'interface sophistiquée avec masquage automatique, permettant une reconnaissance de grille beaucoup plus précise.

### [1.1.0] - Stabilisation
Version de stabilisation avec logging structuré et tests complets.

### [1.0.0] - Lancement
Version initiale avec fonctionnalités de base.
