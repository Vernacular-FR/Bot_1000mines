# ARCHITECTURE COMPLÈTE – Bot 1000mines V2

**Document de référence unique fusionnant ARCHITECTURE.md et V3_COMPARTIMENTE.md**

Cette spécification décrit l'architecture complète du bot 1000mines après la refonte V2. Elle constitue la référence unique pour les décisions techniques et l'organisation du code.

---

## 1. Philosophie et Principes

### Architecture Modulaire
Le projet suit une architecture compartimentée où chaque système a une responsabilité claire et définie. Cette approche facilite la maintenance, l'évolution et la compréhension du codebase.

### Principes de Conception

#### 1. Faible Couplage
- Les modules communiquent via des interfaces claires
- Pas de dépendances circulaires
- Injection de dépendances pour la testabilité

#### 2. Haute Cohésion
- Chaque module a une mission unique et bien définie
- Fonctionnalités regroupées logiquement
- Minimalisation des interdépendances

#### 3. Séparation des Responsabilités
- **Services** : Orchestration métier (session, game loop)
- **Lib** : Bibliothèques spécialisées (pipeline de traitement)
- **SPECS** : Documentation technique unique (source de vérité)

#### 4. Évolutivité
- Architecture ouverte aux extensions
- Pattern Strategy pour les algorithmes
- Pipeline modulaire pour la vision et le solving

---

## 2. Vue d'Ensemble des Couches

### Pipeline V2

```
capture → vision → storage → state_analyzer → solver → planner (execution) → recapture
```

### Les Six Couches du Pipeline

1. **s0_interface** – Pilote le navigateur/canvas (DOM, coordonnées)
   - Expose conversion grille↔écran, navigation viewport
   - Clics JS et lecture statut
   - Reste interchangeable (Selenium aujourd'hui, extension demain)

2. **s1_capture** – Récupère l'image via capture directe du canvas
   - `canvas.toDataURL` + découpe/capture de tuiles 512×512
   - L'assemblage aligné est délégué à `s12_canvas_compositor.py`

3. **s2_vision** – Convertit l'image en grille brute
   - Matching déterministe (CenterTemplateMatcher)
   - Overlays PNG/JSON pour debug
   - **Ne calcule pas la frontière topologique**
   - Marque uniquement `JUST_VISUALIZED` et pousse les révélées dans `known_set`

4. **s3_storage** – Grille sparse unique + index
   - Structure: `{(x,y) → GridCell}`
   - Index: `known_set/revealed_set/active_set/frontier_set/to_visualize_set`
   - Couche passive qui **impose les invariants**
   - **Recalcule les sets incrémentalement**

5. **s4_solver** – Calcule la topologie et décide les actions
   - StateAnalyzer: classification topologique
   - FocusActualizer: promotions de focus (stateless)
   - Réduction/CSP et décisions (SAFE/FLAG/GUESS)
   - **Consomme la frontière depuis storage**

6. **s5_actionplanner** – Agent actif d'exécution
   - Ordonne, traduit et **exécute** les actions en temps-réel
   - Gère les vérifications de vies
   - Délais de stabilisation post-explosion

### Schéma Visuel

```text
┌─────────────────┐
│ s0 Interface    │ ← Selenium + ChromeDriver (DOM, coords)
├─────────────────┤
│ s1 Capture      │ ← Canvas → Image brute (512×512 tiles)
├─────────────────┤
│ s2 Vision       │ ← Template matching → Grille reconnue
├─────────────────┤
│ s3 Storage      │ ← Grid sparse + Sets + Invariants
├─────────────────┤
│ s4 StateAnalyzer│ ← Classification topologique + Focus
├─────────────────┤
│ s4 Solver       │ ← CSP + Propagation → Actions
├─────────────────┤
│ s5 ActionPlanner│ ← Ordonnancement + Exécution
└─────────────────┘
```

---

## 3. Structure du Projet

### Arborescence Complète

```
bot-1000mines/
├── main.py                # Point d'entrée unique
├── src/
│   ├── config.py          # Configuration centralisée
│   ├── services/          # Orchestrateurs métier
│   │   ├── s0_session_service.py  # Gestion session navigateur
│   │   └── s9_game_loop.py        # Boucle de jeu principale
│   └── lib/               # Bibliothèques spécialisées (pipeline)
│       ├── s0_browser/    # Pilote navigateur
│       │   ├── browser.py         # Selenium WebDriver
│       │   ├── actions.py         # Clics, scroll
│       │   └── game_info.py       # Extraction infos jeu
│       ├── s0_coordinates/# Conversion coordonnées
│       │   ├── converter.py       # Grille↔Écran
│       │   ├── viewport.py        # Navigation viewport
│       │   └── canvas_locator.py  # Localisation canvas
│       ├── s0_interface/  # Overlay UI
│       │   └── s07_overlay/       # Canvas HTML5, injection JS
│       ├── s1_capture/    # Capture canvas
│       │   ├── capture.py         # toDataURL
│       │   └── types.py           # CaptureResult, CaptureMeta
│       ├── s2_vision/     # Template matching
│       │   ├── s2_vision.py       # Pipeline vision
│       │   ├── s2a_template_matcher.py  # Matching central
│       │   ├── s2b_gpu_downscaler.py    # GPU/CPU downscaling
│       │   └── templates/         # Templates + manifest
│       ├── s3_storage/    # Grille sparse + sets
│       │   ├── storage.py         # Façade StorageController
│       │   ├── grid.py            # GridStore (sparse grid)
│       │   ├── sets.py            # SetManager (5 sets)
│       │   └── types.py           # GridCell, LogicalCellState
│       ├── s4_solver/     # State analyzer + CSP
│       │   ├── solver.py          # Façade solve()
│       │   ├── runtime_state.py   # Snapshot runtime
│       │   ├── s4a_status_analyzer/  # Classification topologique
│       │   ├── s4b_csp_solver/       # Solveur de contraintes
│       │   └── s4c_overlays/         # Debug overlays
│       └── s5_planner/    # Ordonnancement actions
│           ├── planner.py         # plan() + plan_simple()
│           └── types.py           # PlannerInput, ExecutionPlan
├── tests/                 # Tests unitaires organisés
├── doc/
│   └── SPECS/             # Documentation technique de référence
├── temp/                  # Artefacts de parties (auto-généré)
└── README.md              # Guide utilisateur
```

---

## 4. Flux Détaillé V2

### Étape 1 - Capture (s1)
- Capture des canvases bruts via `CanvasLocator`
- Composition en grille unique via `CanvasCaptureBackend`
- Publication des métadonnées dans `SessionContext`

**Optimisations:**
- Implémentation JavaScript atomique dans `locate_all()` (élimine `StaleElementReferenceException`)
- Calcul positions depuis IDs canvas (ex: canvas_0x0) au lieu des coordonnées DOM

### Étape 2 - Vision (s2)
- `matches_to_upsert()` retourne **seulement les cellules reconnues**
- `solver_status` : JUST_VISUALIZED/NONE/SOLVED
- **Ne calcule plus** frontier/active/known_set (neutralité topologique)

**Optimisations:**
- GPU downscaling (25× plus rapide si torch disponible)
- CPU pre-screening adaptatif (boucles Python < 50k cells, numpy vectorisé > 50k cells)
- Template matching sur zone centrale uniquement

### Étape 3 - Storage (s3)
- `apply_upsert()` valide les invariants (focus levels cohérents)
- `_recalculate_sets()` reconstruit les sets depuis les cellules modifiées
- **Purge automatique de TO_VISUALIZE de active_set**
- Sets gérés : known_set, revealed_set, active_set, frontier_set, to_visualize

**Invariants:**
- Cohérence solver_status/focus levels
- Cohérence logical_state/number_value
- Ordre critique: update cells → recalculate sets

### Étape 4 - State Analyzer (s4a)
- Classification topologique via `FrontierClassifier`
- Promotions : JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED
- **Initialisation des focus levels** (TO_REDUCE/TO_PROCESS)
- `FocusActualizer` gère les promotions de focus (stateless)

**Optimisations:**
- `StatusAnalyzer` ne reclasse que les `JUST_VISUALIZED`
- Focus des FRONTIER/ACTIVE existantes préservés
- `storage.update_from_vision` conserve les focus levels inchangés

### Étape 5 - Solver (s4b)
- Utilise `SolverFrontierView` construite depuis storage
- Consomme `frontier_set` et `frontier_to_process`
- **Ne recalcule plus la frontière localement**
- `compute_frontier_from_cells()` supprimé

**Optimisations:**
- Snapshot runtime unique (mutable + dirty flags)
- Écriture dans storage en fin de pipeline uniquement
- CSP borné via `CSP_CONFIG['max_zones_per_component']=50`

### Étape 6 - Action Planner (s5)
- Ordonne les actions (Flags > Safes > Guess)
- Calcule les coordonnées **relatives à l'anchor**
- Exécute les clics via JS (recalcul de l'absolute en temps-réel)
- Vérifie les vies et applique les délais de stabilisation (2s)

**Gestion erreurs:**
- Mouvement manuel détecté → `success=False` (évite solver avec données périmées)
- Vérification vies après chaque action
- Délai stabilisation post-explosion

---

## 5. Modules Clés V2

### GridStore (s31)
**Responsabilité:** Stockage sparse des cellules

- Sparse grid avec délégation à SetManager
- Validation des invariants dans `_validate_cells()`
- Recalcul incrémental des sets dans `_recalculate_sets()`
- **Ordre correct** : update cells → recalculate sets

### SetManager (s32)
**Responsabilité:** Gestion des 5 sets d'index

- Gère les 5 sets (known, revealed, active, frontier, to_visualize)
- Opérations individuelles pour mises à jour incrémentales
- **Purge TO_VISUALIZE de active_set** dans `apply_set_updates()`

### FocusActualizer (s45)
**Responsabilité:** Promotions de focus (stateless)

- **Module stateless** pour les promotions de focus
- Retourne StorageUpsert avec focus levels mis à jour
- REDUCED → TO_REDUCE, PROCESSED → TO_PROCESS

### StateAnalyzer (s40)
**Responsabilité:** Classification topologique

- Combine classification topologique et promotions focus
- **Instance réutilisable** dans GameLoopService
- Retourne StorageUpsert avec active/frontier mis à jour

### FrontierView Factory
**Responsabilité:** Construction de la vue frontière

- Construit SolverFrontierView depuis storage snapshot
- Filtre frontier_to_process (TO_PROCESS)

---

## 6. Partage des Données

### Structures de Données Clés

#### CaptureMeta
- timestamp
- offset viewport
- taille de cellule
- zoom

#### GridRaw
- dict[(x,y)] = code int
  - 0: fermé
  - -1: drapeau
  - 1..8: numéro
  - 9: vide

#### FrontierSlice
- Sous-ensemble compact
- Densité/priorités
- Metadata viewport

#### ActionBatch
- Liste ordonnée d'actions sûres (flags/open)
- Priorité et contexte

#### PathfinderPlan
- Liste d'actions à exécuter (click/flag/guess)
- Envoyée par s5 vers s6

#### SessionContext
```python
@dataclass
class SessionContext:
    game_id: Optional[str] = None
    iteration: Optional[int] = None
    export_root: Optional[str] = None
    overlay_enabled: bool = False
    capture_saved_path: Optional[str] = None
    capture_bounds: Optional[tuple[int, int, int, int]] = None
    capture_stride: Optional[int] = None
    historical_canvas_path: Optional[str] = None  # V2
```

---

## 7. Invariants Storage

### Cohérence solver_status/focus levels
- **ACTIVE** → focus_level_active in {TO_REDUCE, REDUCED}, focus_level_frontier = None
- **FRONTIER** → focus_level_frontier in {TO_PROCESS, PROCESSED}, focus_level_active = None
- **Others** → focus levels = None

### Cohérence logical_state/number_value
- **OPEN_NUMBER** → number_value obligatoire (1..8)
- **Other** → number_value = None

---

## 8. Performance et Optimisations

### Pipeline Parallèle
- Capture GPU/CPU en parallèle
- Template matching multi-threadé
- Solveur asynchrone

### Mémoire
- Stockage sparse pour la grille
- Cache LRU pour les templates
- Pool d'objets pour les allocations

### UI/Overlay
- RequestAnimationFrame pour 60fps
- Viewport culling pour le rendu
- Canvas interne = CSS (pas de scaling)
- Filtrage cellules UNREVEALED (95%+ des cas) → 20× plus rapide

---

## 9. Gestion des Erreurs

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

---

## 10. Tests et Qualité

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

---

## 11. Avantages de l'Architecture V2

1. **Séparation claire** : chaque module a une responsabilité unique
2. **Pas de doublons** : storage est la source de vérité pour les sets
3. **Extensible** : focus_actualizer peut être enrichi indépendamment
4. **Testable** : chaque module peut être testé isolément
5. **Performance** : recalcul incrémental des sets, pas de calculs redondants
6. **Stateless** : FocusActualizer sans état, plus facile à maintenir
7. **Robuste** : gestion d'erreurs par couches, fallbacks automatiques

---

## 12. Points d'Attention

- La frontière est reconstruite à chaque passe (délai d'une itération après actions solver)
- `frontier_add`/`frontier_remove` vides dans compute_solver_update (géré par storage)
- Focus levels doivent être initialisés lors des promotions dans StateAnalyzer
- Ordre critique dans storage : update cells → recalculate sets
- Overlays reflètent le snapshot runtime réel (suppression des transitions manuelles)

---

## 13. Migration Extension (Futur)

### Préparation Native Messaging
- L'extension envoie `capture` / `solve` / `act` au backend Python via JSON
- Option translation Rust/C++ → WebAssembly pour embarquer la logique côté extension
- Décision à prendre après stabilisation complète

### Overlays Conservés
- PNG/JSON pour être ré-exploités dans une UI pédagogique

---

## 14. Évolutions Prévues

### Court Terme
- Pattern Engine pour reconnaissance avancée
- Mode apprentissage (CNN sur patches)
- Export de statistiques détaillées
- Double-clic SAFE (priorité)
- Marquage `TO_VISUALIZE` après exécution (re-capture ciblée)

### Moyen Terme
- Multi-support (autres sites de démineur)
- Mode compétition (speedrun)
- Interface de configuration avancée
- Stratégies "dumb solver loop" (cliquer les ACTIVE selon FocusLevel)

### Long Terme
- IA reinforcement learning
- Cluster computing pour grille massive
- API REST pour interface externe

---

## 15. Règles d'Implémentation

### Conventions de Nommage
- `facade.py` et `controller.py` sont uniquement des points d'entrée : aucune logique métier
- Toute logique d'une couche vit dans des fichiers préfixés `sXY_` (ex. `s31_grid_store.py`)
- Les modules de debug portent des noms explicites (`debug/overlay_renderer.py`)
- Les tests suivent la convention `tests/test_<couche>_*.py`

### Documentation
- Chaque dossier `src/sX_*` contient `interface.py` décrivant son contrat officiel
- Tests unitaires par couche, référencés dans `tests/` avec README spécifique
- Journaliser les décisions majeures dans `SPECS/DEVELOPMENT_JOURNAL.md`
- Aucune duplication documentaire : `doc/` = résumés, `SPECS/` = référence technique

---

## 16. Roadmap d'Implémentation

**Itération 0** : Nettoyage + création arborescence s0→s6 + `main_simple.py`  
**Itération 1** : s0_interface refactor  
**Itération 2** : s1_capture (canvas toDataURL)  
**Itération 3** : s2_vision (sampler + calibration + debug)  
**Itération 4** : s3_storage (grille sparse + sets + invariants)  
**Itération 5** : s4_solver  
**Itération 6** : s5_actionplanner  
**Itération 7** : s6_action  
**Itération 8** : Extension-ready (interfaces isolées, proto Native Messaging)

---

## 17. Historique des Mises à Jour

### 2025-12-23
- Fusion de ARCHITECTURE.md et V3_COMPARTIMENTE.md
- Document unique de référence créé

### 2025-12-21 (solver/runtime)
- Le solver travaille sur un **snapshot runtime unique** (mutable + dirty flags)
- `StatusAnalyzer` ne reclasse que les `JUST_VISUALIZED`
- `storage.update_from_vision` conserve les focus levels des cellules inchangées
- Overlays reflètent le snapshot runtime réel
- CSP borné via `CSP_CONFIG['max_zones_per_component']=50`

### 2025-12-20 (robustesse & performance)
- **CanvasLocator** : Implémentation JavaScript atomique dans `locate_all()`
- **Positions canvas** : Calcul depuis les IDs au lieu des coordonnées DOM
- **CPU Pre-screening** : Optimisation adaptative
- **Overlay Status** : Filtrage des cellules UNREVEALED → 20× plus rapide
- **Mouvement manuel** : `success=False` pour éviter solver avec données périmées

---

**Cette architecture V2 est maintenant conforme aux SPECS, complètement implémentée et fonctionnelle.**

---

## Références

- `doc/SPECS/s3_STORAGE.md` - Détails storage
- `doc/SPECS/s4_SOLVER.md` - Détails solver
- `doc/SPECS/PIPELINE.md` - Pipeline complet
- `doc/SPECS/DEVELOPMENT_JOURNAL.md` - Journal de bord
