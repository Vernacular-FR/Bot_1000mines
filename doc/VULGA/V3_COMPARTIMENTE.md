# V3 - Architecture Compartimentée

## Philosophie

Le projet Bot 1000mines suit une architecture modulaire où chaque système a une responsabilité claire et définie. Cette approche facilite la maintenance, l'évolution et la compréhension du codebase.

## Structure Principale

```
Bot 1000mines-com/
├── README.md              # Guide utilisateur simple
├── main.py                # Point d'entrée unique
├── src/                   # Cœur technique modulaire
│   ├── lib/               # Bibliothèques spécialisées
│   │   ├── s0_interface/  # Interaction utilisateur et UI
│   │   ├── s1_navigation/ # Contrôle navigateur et DOM
│   │   ├── s2_vision/     # Reconnaissance visuelle et IA
│   │   ├── s3_storage/    # Gestion des données et états
│   │   ├── s4_solver/     # Logique de résolution et algorithmes
│   │   └── s5_config/     # Configuration centralisée
│   └── services/          # Services métier unifiés
│       ├── s9_game_loop.py # Orchestration principale
│       └── s8_planner.py   # Planification stratégique
├── SPECS/                 # Documentation technique unique
└── tests/                 # Tests unitaires organisés
```

## Les Cinq Piliers Modulaires

### s0_interface - Couche Présentation
**Responsabilité** : Interaction avec l'utilisateur et affichage visuel

- **s07_overlay/** : Surcouche visuelle dynamique
  - Canvas HTML5 pour le rendu temps réel
  - Système de coordonnées adaptatif (anchor/controller)
  - Modes d'affichage : status, actions, probabilités
- **ui_controller.py** : Pont Python/JavaScript
- Injection sécurisée du code UI dans le navigateur

### s1_navigation - Couche Contrôle
**Responsabilité** : Navigation et manipulation du DOM

- **selenium_driver.py** : Abstraction Selenium
- **js_executor.py** : Exécution JavaScript optimisée
- Gestion des timeouts, retries et erreurs réseau
- Actions atomiques (click, scroll, attente)

### s2_vision - Couche Perception
**Responsabilité** : Extraction d'informations depuis l'écran

- **s2a_capture.py** : Capture multi-canvas
- **s2b_gpu_downscaler.py** : Optimisation GPU/CPU
- **s2c_template_matcher.py** : Reconnaissance de motifs
- Pipeline de vision : capture → preprocessing → matching → grid

### s3_storage - Couche Données
**Responsabilité** : Gestion d'état et persistance

- **grid.py** : Stockage sparse des cellules
- **storage.py** : Façade simplifiée
- Sets optimisés : frontier, active, revealed, known
- Mises à jour atomiques et cohérence

### s4_solver - Couche Intelligence
**Responsabilité** : Résolution logique et algorithmique

- **s4a_csp_manager.py** : Solveur de contraintes
- **s4b_probability_engine.py** : Calculs probabilistes
- **s4c_pattern_engine.py** : Reconnaissance de motifs (futur)
- Pipeline solver : vision → post-processing → CSP → actions

## Services d'Orchestration

### s9_game_loop - Chef d'Orchestre
- Boucle de jeu principale avec gestion d'état
- Intégration UI (pause/restart)
- Gestion des erreurs et récupération
- Export des données et statistiques

### s8_planner - Stratège
- Scénarios de jeu (PRUDENT, AGGRESSIVE, DESPERATE)
- Burst exploration adaptative
- Gestion des vies et prise de risque
- Planification séquentielle des actions

## Principes de Conception

### 1. Faible Couplage
- Les modules communiquent via des interfaces claires
- Pas de dépendances circulaires
- Injection de dépendances pour la testabilité

### 2. Haute Cohésion
- Chaque module a une mission unique et bien définie
- Fonctionnalités regroupées logiquement
- Minimalisation des interdépendances

### 3. Documentation Unique
- **SPECS/** est la source de vérité technique
- README.md pour l'utilisateur final
- Pas de duplication d'information

### 4. Évolutivité
- Architecture ouverte aux extensions
- Pattern Strategy pour les algorithmes
- Pipeline modulaire pour la vision et le solving

## Flux de Données Typique

```
Navigation → Vision → Storage → Solver → Planner → UI
    ↑           ↓        ↓        ↓        ↓
    └──────────────────────────────────────┘
                 Game Loop
```

1. **Navigation** capture la page
2. **Vision** extrait la grille
3. **Storage** met à jour l'état
4. **Solver** calcule les actions
5. **Planner** ordonne les actions
6. **UI** affiche les résultats

## Gestion des Erreurs

### Stratégie par Couches
- **Interface** : Messages utilisateur, toast notifications
- **Navigation** : Retries automatiques, fallbacks
- **Vision** : Calibration dynamique, seuils adaptatifs
- **Storage** : Validation d'état, rollback
- **Solver** : Mode dégradé, heuristiques de secours

### Logging Structuré
- Logs agrégés (pas d'énumérations exhaustives)
- Niveaux : DEBUG, INFO, WARNING, ERROR
- Contexte : module, fonction, timestamp

## Performance et Optimisations

### Pipeline Parallèle
- Capture GPU/CPU en parallèle
- Template matching multi-threadé
- Solveur asynchrone

### Mémoire
- Stockage sparse pour la grille
- Cache LRU pour les templates
- Pool d'objets pour les allocations

### UI
- RequestAnimationFrame pour 60fps
- Viewport culling pour le rendu
- Canvas interne = CSS (pas de scaling)

## Tests et Qualité

### Organisation des Tests
```
tests/
├── test_vision.py      # Tests unitaires vision
├── test_solver.py      # Tests algorithmes
├── test_storage.py     # Tests persistance
└── run_all_tests.py    # Lanceur automatique
```

### Stratégie de Test
- Tests unitaires isolés par module
- Tests d'intégration pour les pipelines
- Tests E2E pour les scénarios complets

## Évolutions Prévues

### Court Terme
- Pattern Engine pour reconnaissance avancée
- Mode apprentissage (CNN sur patches)
- Export de statistiques détaillées

### Moyen Terme
- Multi-support (autres sites de démineur)
- Mode compétition (speedrun)
- Interface de configuration avancée

### Long Terme
- IA reinforcement learning
- Cluster computing pour grille massive
- API REST pour interface externe

Cette architecture compartimentée assure une base solide pour les développements futurs tout en maintenant une codebase propre et compréhensible.
