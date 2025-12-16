# Journal de Développement - Bot Minesweeper

## 🎯 Ce Document

**Journal + Roadmap du projet** : Ce fichier contient :
- **Ce qui a été fait** (sessions de développement)
- **Erreurs rencontrées** et solutions trouvées
- **Ce qui est prévu** (roadmap future)
- **Leçons apprises** pour le développement

*C'est le document de référence pour le suivi actif du projet.*

---

## Session du 16 Décembre 2025 (Fusion reducer + CSP dans GameLoopService)

### Objectif principal
Intégrer les actions du reducer dans le pipeline d'exécution du jeu pour que toutes les actions sûres soient appliquées, pas seulement celles du CSP.

### Actions clés
- Ajout de `solve_snapshot_with_reducer_actions` dans `StorageSolverService` pour exposer les `reducer_actions` en tant que `SolverAction`
- Modification de `GameLoopService.execute_single_pass` pour fusionner `reducer_actions` + `solver_actions` avant planification
- Priorisation des actions déterministes (CLICK/FLAG) avant les GUESS
- Augmentation de `max_component_size` à 500 pour traiter des frontières plus grandes
- Consolidation des overlays sur `s1_capture/s10_overlay_utils.setup_overlay_context` (suppression d'`overlay_test_utils.py`)
- Correction des tests 02/04/05 : signature (`screenshot_path`, `overlay_enabled=True`) et imports `CspManager`

### Résultats
- Le bot exécute maintenant toutes les actions sûres (reducer + CSP) avant un éventuel guess
- Les logs montrent bien les reducer_actions avec le tag `frontiere-reducer`
- Les tests unitaires génèrent correctement leurs overlays
- Pipeline principal fonctionnel avec 24 actions exécutées (incluant les reducer actions)

### Documentation (même session)
- Alignement de `doc/SPECS/*` sur un modèle didactique unique (`doc/SPECS/s3_STORAGE.md`).
- Mise à jour des notions storage : `revealed_set / active_set / frontier_set`.
- Nomenclature FocusLevel : `TO_TEST/TESTED/STERILE` et `TO_PROCESS/PROCESSED/BLOCKED`.
- ZoneDB formalisée comme index dérivé (pilotage CSP via zones `TO_PROCESS`).
- Référence dumb solver loop consolidée dans `src/services/s44_dumb_solver_loop.md`.

---

### Objectif principal
Aligner le pipeline runtime sur la refonte CSP testée : capture live, vision, stockage, solver + overlays cohérents, fermeture session unique.

### Actions clés
- `bot_1000mines.py` et `main.py` délèguent capture→vision→solver à `ZoneCaptureService`, `VisionAnalysisService`, `GameSolverServiceV2`.
- Overlays solver routés dans `temp/games/{id}/s4_solver/` : `s40_states_overlays`, `s42_segmentation_overlay`, `s43_csp_combined_overlay` (actions reducer opaques, guesses croix blanche).
- `CspManager` transmet les actions reducer au combiné ; `s494_combined_overlay` rend opaque reducer + CSP, inclut guesses.
- `SessionStorage.build_game_paths` définit les dossiers overlays; `cleanup_session` n’est appelé qu’en fin de run (prompt Entrée avant fermeture navigateur).

### Résultats
- Pipeline principal génère à nouveau tous les overlays (vision + états + segmentation + combiné) dans l’arborescence de partie.
- Réduction CSP visible dans le combiné ; guesses plus lisibles.
- Fin de session maîtrisée par le pilote principal (pas de cleanup dans la boucle).

### Points d’attention
- Conserver `overlay_enabled=True` pour produire les dossiers overlays par partie.
- Vérifier les chemins `s4_solver/…` lors de nouveaux tests ou changement d’arborescence.

---

## Session du 14 Décembre 2025 (CSP Optimized Solver & Benchmarks)

### Objectif principal
Remplacer l’ancien hybrid solver par un pipeline CSP optimisé autonome, instrumenter des scripts de comparaison et préparer la future phase Pattern Solver.

### Actions clés
- Renommage/portage de `s49_hybrid_solver.py` → `s49_optimized_solver.py` exécutant uniquement `CspManager.run_with_frontier_reducer()`.
- Ajout d’options `use_stability` + `ComponentRangeConfig` dans `CspManager` pour lever les garde-fous ou ajuster la taille max (50 cases par défaut).
- Scripts de bench :
  - `01_run_propagation_solver.py` & `02_run_csp_solver_only.py` utilisent les overlays bi-opacité (phase 1 vs phases avancées / reducer vs CSP).
  - `03_compare_solver_pipelines.py` compare Propagator vs CSP (safe/flags, temps absolu, ratio, rapport JSON + Markdown avec moyennes).
- Création de `s43_pattern_solver/IMPLEMENTATION_PLAN.md` (plan futur tests, overlays, intégration dans `03_compare...`).
- Extension Native Messaging (content script) pour capturer le canvas et afficher les overlays PNG/JSON.
- Backend Python réduit aux services s2→s6, invocable en CLI/daemon.
- Tests d’intégration headless (Playwright) pour valider les overlays et les actions.
- Clarifier responsabilités : modules `lib/*` portent la logique (chemins overlay, suffixes, calculs) ; controllers = passe-plats ; services = orchestration (export_root unique fourni par SessionStorage).

### Résultats
- CSP isolé atteint les mêmes actions que le propagator sur les patterns testés, tout en étant ~3x plus rapide (cf. `solver_comparison_YYYYMMDD_HHMMSS.md`).
- Les overlays CSP affichent désormais les actions du reducer (translucides) et du CSP (opaques), ce qui facilite la relecture.
- La roadmap Pattern Solver dispose d’un plan dédié (tests `04_run_pattern_solver_only.py`, extension du comparateur, intégration future dans `OptimizedSolver`).

### Points d’attention
- Garder `use_stability=False` pour les campagnes de bench afin de ne pas filtrer les composantes intéressantes.
- Prévoir l’intégration du Pattern Solver dans `OptimizedSolver` une fois les scripts 04/03 étendus.
- Mettre à jour les documents de référence (CHANGELOG, PIPELINE, SPECS) dès que de nouvelles phases sont implémentées.

---

## Session du 12 Décembre 2025 (Validation Vision S2)

### Objectif principal
Valider le pipeline **CenterTemplateMatcher** end-to-end, intégrer `question_mark`, verrouiller les seuils (empty=25) et finaliser les overlays pour audit visuel.

### Actions clés
- Implémentation de l’ordre de priorité + early exit dans `s21_template_matcher.py`.
- Heuristique discriminante `exploded` via pixel périphérique, ajout `question_mark` aux seuils uniformes.
- Resserrement du seuil `empty` (25) pour couper les décors gris clairs repérés dans les captures réelles.
- Overlays : couleurs explicites (question_mark = blanc, decor = gris/noir) et label + pourcentage compactés (font 11, spacing maîtrisé).
- Tests `tests/test_s2_vision_performance.py` rejoués en boucle jusqu’à obtenir 100 % de reconnaissance stable (question marks inclus).
- Documentation mise à jour (`s02_VISION_SAMPLING.md`, `s21_templates_analyzer/READ_ME.md`, `PLAN_S2_VISION_PURGE.md`) + entrée dédiée dans `doc/META/CHANGELOG.md`.

### Extension Capture Alignée (même session)
- Délégation complète des captures multi-canvases à `ZoneCaptureService.capture_canvas_tiles`.
- Création du module `src/lib/s1_capture/s12_canvas_compositor.py` (alignement cell_ref, ceil/floor, recalcul `grid_bounds`).
- Suppression de la logique de collage dans `bot_1000mines.py` + suppression des anciens overlays de debug côté capture.
- Documentation mise à jour (CHANGELOG, doc/SPECS) pour refléter cette architecture.

### Résultats
- Vision API validée : plus aucun `question_mark` classé décor, empty uniquement quand bord blanc confirmé.
- Overlays lisibles en production (couleurs cohérentes, pourcentage aligné).
- Temps moyen par screenshot <0,6 s (machine de référence) après la purge des logs de debug.
- Dossier `debug_question_mark/` nettoyé (plus de dumps nécessaires).

### 🚨 Points d’attention
- Maintenir la discipline : chaque ajustement de seuil (ex. empty) doit être documenté + benché.
- Conserver le dataset question_mark aligné ; en cas d’ajout, regénérer `template_aggregator.py` + manifest.
- Le test perf échoue quand on laisse des prints lourd → vérifier qu’aucun debug ne traîne avant commit.

---

## 📅 Session du 10 Décembre 2025 (Plan de simplification radicale)

### 🎯 Objectif principal
Repartir d’une architecture claire en 7 couches (s0→s6), aligner toute la documentation (`doc/`, `SPECS/`), préparer l’itération 0 et acter la future migration vers extension/Native Messaging.

### ✅ Actions clés
- Synthèse unique (`development/SYNTHESE_pipeline_refonte.md`) pour figer les décisions capture/vision/solver/actionplanner.
- Recréer `doc/` avec fichiers numérotés (README + 01/02/03) orientés pilotage rapide.
- Générer `SPECS/ARCHITECTURE.md` (pipeline + arborescence) et `SPECS/CHANGELOG.md` mis à jour.
- Initialiser `SPECS/ROADMAP.md` (ce document) avec la nouvelle feuille de route.
- Archiver les notes historiques dans `backups/` et pointer `doc/`/`SPECS/` depuis `.gitignore`.

### 📊 Résultats
- Plan validé (capture canvas direct, storage trois sets, solver local, actionplanner prioritaire).
- Documentation séparée : résumés dans `doc/`, référence technique dans `SPECS/`.
- Itérations 0→8 prêtes à être lancées (voir section “Roadmap Simplification” ci-dessous).

### 🚨 Points d’attention
- Prendre un backup complet avant de démarrer l’itération 0.
- Prioriser la capture via `canvas.toDataURL`/CDP (Selenium legacy uniquement si nécessaire).
- Tenir `SPECS/DEVELOPMENT_JOURNAL.md` à jour après chaque itération.

---

## 📅 Session du 2 Décembre 2025 (Correction Système Coordonnées)

### **🎯 Objectif Principal**
Résoudre les erreurs "move target out of bounds" et stabiliser le système de clics du bot.

---

## 🔄 Actions Réalisées

### **Phase 1: Diagnostic Coordonnées (22h00-22h20)**
- ✅ **Identification problème** : `ActionChains.move_by_offset()` utilise offsets relatifs
- ✅ **Debug coordonnées** : Ajout affichage taille fenêtre (2576x1416) et position anchor
- ✅ **Sélecteur corrigé** : `canvas` → `#anchor` (élément correct avec x=980, y=806)
- ✅ **JavaScript vs Selenium** : Analyse des alternatives via MCP Context7

### **Phase 2: Solution JavaScript (22h20-22h30)**
- ✅ **GameController.click_cell** : Intégration de la méthode existante avec JavaScript MouseEvent
- ✅ **Remplacement ActionChains** : `move_by_offset()` → `click_cell()` natif
- ✅ **Coordonnées CSS** : `getBoundingClientRect()` au lieu de `element.rect`
- ✅ **Architecture unifiée** : Navigation (`move_view_js`) + Clics (`click_cell`) tous en JavaScript

### **Phase 3: Validation (22h30-22h40)**
- ✅ **Tests successifs** : 23/23 actions réussies → 27/27 actions réussies
- ✅ **Stabilité confirmée** : Temps d'exécution 2.40s constant
- ✅ **Documentation mise à jour** : Changelog v2.4.0 et journal de développement

---

## 📊 Métriques de la Session

- **Durée totale** : 40 minutes
- **Taux de réussite** : 0% → 100% (27/27 actions)
- **Temps d'exécution** : 2.40s stable
- **Erreurs éliminées** : Plus de "move target out of bounds"
- **Fichiers modifiés** : 2 (coordinate_system.py, s4_action_executor_service.py)

---

## 🎯 Résultats Atteints

### **Bot 100% Fonctionnel**
```bash
[ACTION] Exécution terminée: 27/27 actions réussies en 2.40s
[SUCCES] Actions exécutées: 27/27
   Temps: 2.40s
```

### **Architecture JavaScript Native**
- **Navigation** : `move_view_js()` (JavaScript natif)
- **Clics** : `click_cell()` (JavaScript MouseEvent)
- **Conversion** : `CoordinateSystem` avec anchor CSS correct

### **Fiabilité Maximale**
- Coordonnées positives garanties (x=980, y=806)
- Plus d'erreurs de coordonnées négatives
- Prêt pour développement game loop itératif

---

## 🚨 Décisions Techniques

### **Décision 1: JavaScript vs Selenium**
- **Choix** : JavaScript MouseEvent > ActionChains
- **Raison** : Canvas games nécessitent événements natifs
- **Résultat** : 100% de taux de réussite

### **Décision 2: GameController Réutilisation**
- **Choix** : Utiliser `click_cell()` existant
- **Raison** : Méthode déjà parfaite avec JavaScript
- **Résultat** : Cohérence architecture + fiabilité

### **Décision 3: Anchor CSS**
- **Choix** : `getBoundingClientRect()` + `#anchor`
- **Raison** : Coordonnées viewport fiables
- **Résultat** : Conversion grille→écran parfaite

---

## 🎯 Prochaines Étapes

### **Priorité 1: Game Loop Itératif**
- [ ] **Développement boucle complète** : Analyse → Action → Capture → Répéter
- [ ] **Gestion état persistant** : Base de données cellules entre itérations
- [ ] **Optimisation temps réel** : Réduction délais entre captures/actions

### **Priorité 2: Robustesse**
- [ ] **Gestion erreurs jeu** : Game over, victoire, changements d'état
- [ ] **Validation actions** : Vérification clics effectifs
- [ ] **Monitoring performance** : Temps par itération, taux de réussite

### **Priorité 3: Intelligence**
- [ ] **Stratégies avancées** : Probabilités, patterns complexes
- [ ] **Apprentissage** : Adaptation selon difficulté
- [ ] **Optimisation parcours** : Ordre optimal des clics

---

## 🎯 Leçons Apprises

### **JavaScript Natif**
- **Canvas games** : JavaScript plus fiable que Selenium
- **MouseEvent** : Événements souris natifs essentiels
- **getBoundingClientRect()** : Coordonnées viewport précises

### **Architecture**
- **Cohérence** : Navigation + clics doivent utiliser même technologie
- **Réutilisation** : `GameController.click_cell` était déjà parfait
- **Simplicité** : Moins de code = moins d'erreurs

### **Debug**
- **Logs détaillés** : Essentiels pour identifier problèmes
- **Tests itératifs** : Validation progressive des solutions
- **Documentation** : Changelog maintenu en temps réel

---

## 📝 Notes de Session

**Cette session a transformé un bot non fonctionnel (0% de réussite) en un bot 100% opérationnel. La clé : utiliser JavaScript natif pour les interactions Canvas plutôt que Selenium ActionChains.**

**Le bot est maintenant prêt pour le développement du game loop itératif complet.**

---

## 📅 Sessions Précédentes

### **30 Novembre 2025 (Architecture Modulaire)**
- Refactoring majeur vers architecture modulaire
- Séparation des responsabilités services/lib
- Documentation technique initiale

### **29 Novembre 2025 (Interface Intelligente)**
- Détection automatique d'interface
- Masquage intelligent des éléments UI
- Reconnaissance de grille précise

## 🛣️ Roadmap Simplification (itérations planifiées)

| Itération | Objectif | Livrables clés |
|-----------|----------|----------------|
| **0 – Nettoyage & nomenclature** | Archiver l’ancien CNN, purger les services legacy, consolider l’arborescence `src/lib/s0_interface … s6_action`. | Arborescence propre + points d’entrée stabilisés. |
| **1 – s0 Interface** | Stabiliser `src/lib/s0_interface` (coords, anchor, navigation JS, capture meta). | API interface officielle + invariants de conversion. |
| **2 – s1 Capture** | Capture canvas (`canvas.toDataURL`) + assemblage aligné (`s12_canvas_compositor.py`). | `src/lib/s1_capture/*`, service `ZoneCaptureService`. |
| **3 – s2 Vision** | CenterTemplateMatcher + overlays runtime + tests perf. | `src/lib/s2_vision/*`, templates analyzers + manifest. |
| **4 – s3 Storage** | Grille sparse + SetManager (revealed/active/frontier) + invariants. | `src/lib/s3_storage/*` + exports JSON. |
| **5 – s4 Solver** | Grid Analyzer + CSP optimisé (OptimizedSolver) + bench scripts. | `src/lib/s4_solver/s40_*/s42_*/s49_optimized_solver.py`. |
| **6 – s5 Actionplanner** | Heatmap, barycentres, déplacements multi-étapes. | `src/lib/s5_actionplanner/*`. |
| **7 – s6 Action** | Exécuteur d’actions (JS natif/Selenium) + reporting. | `src/lib/s6_action/*`. |
| **8 – Extension-ready** | Interfaces isolées, PoC Native Messaging / WebExtension, endpoints stable. | Spéc proto extension + doc API. |

---

## ✅ Backlog prioritaire post-plan

1. **Backup complet** de l’état actuel (code + données) avant itération 0.
2. **Itération 0** : création des dossiers s0→s6, suppression des services historiques, `main_simple.py`.
3. **Journalisation** : re-créer `SPECS/DEVELOPMENT_JOURNAL.md` (supprimé) et y logguer chaque itération.
4. **Tests** : définir le squelette `tests/run_all_tests.py` pour couvrir chaque couche progressivement.
5. **Préparation extension** : lister les endpoints nécessaires pour Native Messaging (capture/solve/act).

---

## 📌 Rappels

- `doc/` = synthèses opérationnelles. `SPECS/` = référence technique exhaustive.
- Tenir `CHANGELOG.md` synchronisé avec chaque entrée du journal.
- Toujours privilégier capture canvas direct + actionplanner basé sur la frontière compacte.
