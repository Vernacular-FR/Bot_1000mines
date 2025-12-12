# Journal de Développement - Bot Minesweeper

## 🎯 Ce Document

**Journal + Roadmap du projet** : Ce fichier contient :
- **Ce qui a été fait** (sessions de développement)
- **Erreurs rencontrées** et solutions trouvées
- **Ce qui est prévu** (roadmap future)
- **Leçons apprises** pour le développement

*C'est le document de référence pour le suivi actif du projet.*

---

## 📅 Session du 12 Décembre 2025 (Validation Vision S2)

### 🎯 Objectif principal
Valider le pipeline **CenterTemplateMatcher** end-to-end, intégrer `question_mark`, verrouiller les seuils (empty=25) et finaliser les overlays pour audit visuel.

### ✅ Actions clés
- Implémentation de l’ordre de priorité + early exit dans `s21_template_matcher.py`.
- Heuristique discriminante `exploded` via pixel périphérique, ajout `question_mark` aux seuils uniformes.
- Resserrement du seuil `empty` (25) pour couper les décors gris clairs repérés dans les captures réelles.
- Overlays : couleurs explicites (question_mark = blanc, decor = gris/noir) et label + pourcentage compactés (font 11, spacing maîtrisé).
- Tests `tests/test_s2_vision_performance.py` rejoués en boucle jusqu’à obtenir 100 % de reconnaissance stable (question marks inclus).
- Documentation mise à jour (`s02_VISION_SAMPLING.md`, `s21_templates_analyzer/READ_ME.md`, `PLAN_S2_VISION_PURGE.md`) + entrée dédiée dans `doc/META/CHANGELOG.md`.

### 🔧 Extension Capture Alignée (même session)
- Délégation complète des captures multi-canvases à `ZoneCaptureService.capture_canvas_tiles`.
- Création du module `lib/s1_capture/s12_canvas_compositor.py` (alignement cell_ref, ceil/floor, recalcul `grid_bounds`).
- Suppression de la logique de collage dans `bot_1000mines.py` + suppression des overlays debug (`s12_grid_overlay.py`, `annotate_grid`).
- Documentation mise à jour (CHANGELOG, INDEX lib/) pour refléter cette architecture.

### 📊 Résultats
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
- Synthèse unique (`development/SYNTHESE_pipeline_refonte.md`) pour figer les décisions capture/vision/solver/pathfinder.
- Recréer `doc/` avec fichiers numérotés (README + 01/02/03) orientés pilotage rapide.
- Générer `SPECS/ARCHITECTURE.md` (pipeline + arborescence) et `SPECS/CHANGELOG.md` mis à jour.
- Initialiser `SPECS/ROADMAP.md` (ce document) avec la nouvelle feuille de route.
- Archiver les notes historiques dans `backups/` et pointer `doc/`/`SPECS/` depuis `.gitignore`.

### 📊 Résultats
- Plan validé (capture canvas direct, storage double, solver local, pathfinder prioritaire).
- Documentation séparée : résumés dans `doc/`, référence technique dans `SPECS/`.
- Itérations 0→8 prêtes à être lancées (voir section “Roadmap Simplification” ci-dessous).

### 🚨 Points d’attention
- Prendre un backup complet avant de démarrer l’itération 0.
- Prioriser la capture via `canvas.toDataURL`/CDP (Selenium legacy uniquement si nécessaire).
- Tenir `SPECS/DEVELOPMENT_JOURNAL.md` à jour après chaque itération.

---

### **Session historique – Exploitation CNN (archive `backups/src`)**
- Pipeline CNN complet conservé dans `backups/src/` : acquisition Selenium → prétraitements multi-passes → réseau `s22_Neural_engine`.
- Génération datasets automatisée (scripts `augment_borders.py`, `prepare_cnn_dataset.py`) + templates stockés dans `assets/symbols/`.
- Services associés : `s2_optimized_analysis_service.py`, overlays lourds, base JSON des cellules analysées.
- Statut : **archivé** pour référence/fallback. Le plan actuel (sampling + solver déterministe) remplace ce pipeline dans la boucle principale, mais la version CNN reste exploitable en laboratoire (réentraînement, comparaison perf).

---

## 📅 Session du 1 Décembre 2024 (Refactoring Documentation)

### **🎯 Objectif Principal**
Créer une documentation technique complète et organiser les opérateurs de la bibliothèque `lib/`.

---

## 🔄 Actions Réalisées

### **Phase 1: Documentation des Opérateurs (12:00-12:20)**
- ✅ **Analyse complète lib/** : Scan de tous les fichiers Python pour extraire les méthodes
- ✅ **65+ méthodes documentées** : Coordinate System, Game Controller, Browser Manager, etc.
- ✅ **lib/INDEX.md créé** : Documentation complète avec descriptions détaillées
- ✅ **Structure hiérarchique** : Core Bot (3 modules), Utilities (2 modules), Vision (6 modules)

### **Phase 2: Organisation Documentation (12:20-12:30)**
- ✅ **docs/specs/operateurs_lib.md** : Création fichier dédié puis déplacement
- ✅ **lib/INDEX.md** : Placement optimal directement avec le code
- ✅ **docs/specs/composants_techniques.md** : Mise à jour avec lien vers `../lib/INDEX.md`
- ✅ **Références croisées** : Navigation fluide entre documentation

### **Phase 3: Mise à jour Architecture (12:30-12:40)**
- ✅ **architecture_logicielle.md** : Ajout TestPatternsService et nouveaux modules
- ✅ **Nouveaux noms** : screenshot_manager, grid_analyzer_overlay, interface_detector
- ✅ **Vision restructuré** : Documentation des 4 modules recognition/
- ✅ **Patterns architecturaux** : Ajout Template Method Pattern

### **Phase 4: Meta Documentation (12:40-12:45)**
- ✅ **changelog.md** : Ajout section [Unreleased] avec toutes les nouveautés
- ✅ **roadmap.md** : Documentation de cette session
- ✅ **Version 1.4.0** : Préparation avec nouvelles fonctionnalités

---

## 📊 Métriques de la Session

- **Durée totale** : 45 minutes
- **Fichiers créés** : 1 (lib/INDEX.md)
- **Fichiers modifiés** : 3 (architecture_logicielle.md, composants_techniques.md, changelog.md, roadmap.md)
- **Méthodes documentées** : 65+ méthodes complètes
- **Modules couverts** : 11 modules techniques
- **Lignes de documentation** : ~300 lignes détaillées

---

## 🎯 Résultats Atteints

### **Documentation Complète**
```
lib/
├── INDEX.md (65+ méthodes documentées)
├── bot/ (Coordinate System, Game Controller, Browser Manager)
├── vision/ (6 modules spécialisés)
└── performance_monitor.py
```

### **Architecture Documentée**
- **TestPatternsService** intégré dans l'architecture complète
- **Vision restructuré** avec modules recognition/
- **Patterns architecturaux** mis à jour
- **Flux de données** enrichis avec nouveaux services

### **Navigation Optimisée**
- **lib/INDEX.md** : Référence principale pour les développeurs
- **docs/specs/** : Vue d'ensemble avec liens croisés
- **Références** : Navigation fluide entre tous les documents

---

## 🚨 Décisions Techniques

### **Décision 1: lib/INDEX.md vs docs/specs/**
- **Choix** : Placer INDEX.md directement dans lib/
- **Raison** : Proximité code/documentation pour les développeurs
- **Résultat** : Navigation naturelle et maintenance facilitée

### **Décision 2: Documentation détaillée**
- **Choix** : Documenter chaque méthode avec description
- **Raison** : Référence complète pour développement futur
- **Résultat** : 65+ méthodes avec signatures et utilité

### **Décision 3: Architecture mise à jour**
- **Choix** : Intégrer TestPatternsService dans docs officiels
- **Raison** : Refactoring terminé, architecture stabilisée
- **Résultat** : Documentation cohérente avec code actuel

---

## 🎯 Prochaines Étapes

### **Priorité 1: Stabilisation**
- [ ] **Tester la nouvelle architecture** avec scénario 1 complet
- [ ] **Valider les nouveaux noms** de modules vision
- [ ] **Vérifier les références** croisées dans toute la documentation

### **Priorité 2: Fonctionnalités**
- [ ] **Service de reconnaissance** cellules (basé sur modules vision/)
- [ ] **Tests avancés** viewport (patterns complexes)
- [ ] **Monitoring performance** intégré aux services

### **Priorité 3: Qualité**
- [ ] **Tests unitaires** pour tous les nouveaux modules
- [ ] **Documentation utilisateur** (README.md simplifié)
- [ ] **Intégration continue** avec validation documentation

---

## 🎯 Leçons Apprises

### **Documentation**
- **Proximité code/doc** : INDEX.md dans lib/ est plus efficace
- **Descriptions détaillées** : Essentiel pour référence future
- **Références croisées** : Navigation fluide entre documents

### **Architecture**
- **Refactoring progressif** : TestPatternsService est maintenant stable
- **Noms cohérents** : screenshot_manager plus clair que screenshot_capture
- **Patterns réutilisables** : Template Method pour tests

### **Organisation**
- **Meta documentation** : Changelog et roadmap maintenus à jour
- **Versions sémantiques** : 1.4.0 pour nouvelles fonctionnalités
- **Structure évolutive** : Documentation prête pour extensions futures

---

## 📝 Notes de Session

**Cette session a transformé la documentation technique d'un état fragmenté à une référence complète et organisée. Les développeurs ont maintenant accès à 65+ méthodes documentées avec une navigation intuitive.**

**Le plus important : maintenir cette discipline de documentation lors des futurs développements.**

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
| **0 – Nettoyage & nomenclature** | Archiver l’ancien CNN, purger les services legacy, créer les dossiers `src/s0_viewport ... s6_action` + `main_simple.py`. | Arborescence propre + boucle `main_simple` squelette. |
| **1 – s0 Interface** | Refactor `lib/s0_navigation` en `src/s0_viewport/viewport_controller.py`. | Pilotage DOM/coords unifié + interface officielle. |
| **2 – s1 Capture** | Implémenter `canvas.toDataURL`, fallback CDP, purge buffers. | `src/s1_capture/canvas_capture.py`, tests simples. |
| **3 – s2 Vision** | LUT + pixel sampler + calibration auto + overlays. | `pixel_sampler.py`, `calibration.py`, dossier debug. |
| **4 – s3 Storage** | Double base (archive + frontière compacte) + densité pour pathfinder. | `grid_store.py`, `serializers.py`, interface. |
| **5 – s4 Solver** | Motifs déterministes + solveur exact local + debug overlays. | `pattern_engine.py`, `local_solver.py`, exports PNG/JSON. |
| **6 – s5 Pathfinder** | Heatmap, barycentres, déplacements multi-étapes, prise en compte des zones hors écran. | `pathfinder.py`, interface + heuristique densité. |
| **7 – s6 Action** | Exécuteur d’actions multi-clics + reporting. | `click_executor.py`, interface, scénarios Selenium. |
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
- Toujours privilégier capture canvas direct + pathfinder basé sur la frontière compacte.
