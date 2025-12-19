# ARCHITECTURE – Référence officielle V2

Cette spécification décrit l'architecture du bot 1000mines après la refonte V2. Elle constitue la référence unique pour les décisions techniques. L'architecture V2 implémente un pipeline modulaire clair avec séparation stricte des responsabilités.

## 1. Vue d'ensemble des couches

1. **s0_interface** – Pilote le navigateur/canvas (DOM, coordonnées). Expose conversion grille↔écran, navigation viewport, clics JS et lecture statut. Reste interchangeable (Selenium aujourd'hui, extension demain).
2. **s1_capture** – Récupère l'image via capture directe du canvas (`canvas.toDataURL`) + découpe/capture de tuiles 512×512. L'assemblage aligné est délégué à `src/lib/s1_capture/s12_canvas_compositor.py`.
3. **s2_vision** – Convertit l'image en grille brute via matching déterministe (CenterTemplateMatcher) + overlays PNG/JSON. **Ne calcule pas la frontière topologique**, marque uniquement `JUST_VISUALIZED` et pousse les révélées dans `known_set`.
4. **s3_storage** – Grille sparse unique `{(x,y) → GridCell}` + index `known_set/revealed_set/active_set/frontier_set/to_visualize_set`. Couche passive qui **impose les invariants** (logical ↔ number_value, focus ↔ solver_status) et **recalcule les sets incrémentalement**.
5. **s4_solver** – Calcule la topologie (via StateAnalyzer), applique FocusActualizer (stateless), puis réduit/CSP et décide les actions (SAFE/FLAG/GUESS). **Consomme la frontière depuis storage**, ne la recalcule plus localement.
6. **s5_actionplanner** – Planification minimale : ordonne et traduit les actions solver en actions exécutables.
7. **s6_action** – Applique les actions JS.

### Schéma pipeline V2

```
capture → vision → storage → state_analyzer → solver → executor → recapture
```

```text
┌─────────────────┐
│ s0 Interface    │ ← pilote le navigateur / canvas (DOM, coords)
├─────────────────┤
│ s1 Capture      │ ← canvas → raw image (bytes)
├─────────────────┤
│ s2 Vision       │ ← CenterTemplateMatcher → grille brute (JUST_VISUALIZED)
├─────────────────┤
│ s3 Storage      │ ← Grid global + index + invariants + recalcul sets
├─────────────────┤
│ s4 StateAnalyzer│ ← classification topologique + promotions focus
├─────────────────┤
│ s4 Solver       │ ← décisions SAFE/FLAG/GUESS (lit frontier depuis storage)
├─────────────────┤
│ s5 ActionPlanner│ ← ordonne / convertit
├─────────────────┤
│ s6 Action       │ ← exécute clics/scroll
└─────────────────┘
```

## 2. Flux détaillé V2

### Étape 1 - Capture
- Capture des canvases bruts via `CanvasLocator`
- Composition en grille unique via `CanvasCaptureBackend`
- Publication des métadonnées dans `SessionContext`

### Étape 2 - Vision (s2)
- `matches_to_upsert()` retourne **seulement les cellules reconnues**
- `solver_status` : JUST_VISUALIZED/NONE/SOLVED
- **Ne calcule plus** frontier/active/known_set (neutralité topologique)

### Étape 3 - Storage (s3)
- `apply_upsert()` valide les invariants (focus levels cohérents)
- `_recalculate_sets()` reconstruit les sets depuis les cellules modifiées
- **Purge automatique de TO_VISUALIZE de active_set**
- Sets gérés : known_set, revealed_set, active_set, frontier_set, to_visualize

### Étape 4 - State Analyzer (s4)
- Classification topologique via `FrontierClassifier`
- Promotions : JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED
- **Initialisation des focus levels** (TO_REDUCE/TO_PROCESS)
- `FocusActualizer` gère les promotions de focus (stateless)

### Étape 5 - Solver (s4)
- Utilise `SolverFrontierView` construite depuis storage
- Consomme `frontier_set` et `frontier_to_process`
- **Ne recalcule plus la frontière localement**
- `compute_frontier_from_cells()` supprimé

### Étape 6 - Executor
- Exécute les actions (flags, clics)
- Met à jour l'état du jeu

## 3. Modules clés V2

### GridStore (s31)
- Sparse grid avec délégation à SetManager
- Validation des invariants dans `_validate_cells()`
- Recalcul incrémental des sets dans `_recalculate_sets()`
- **Ordre correct** : update cells → recalculate sets

### SetManager (s32)
- Gère les 5 sets (known, revealed, active, frontier, to_visualize)
- Opérations individuelles pour mises à jour incrémentales
- **Purge TO_VISUALIZE de active_set** dans `apply_set_updates()`

### FocusActualizer (s45)
- **Module stateless** pour les promotions de focus
- Retourne StorageUpsert avec focus levels mis à jour
- REDUCED → TO_REDUCE, PROCESSED → TO_PROCESS

### StateAnalyzer (s40)
- Combine classification topologique et promotions focus
- **Instance réutilisable** dans GameLoopService
- Retourne StorageUpsert avec active/frontier mis à jour

### FrontierView Factory
- Construit SolverFrontierView depuis storage snapshot
- Filtre frontier_to_process (TO_PROCESS)

## 4. Partage des données

- `CaptureMeta` : timestamp, offset viewport, taille de cellule, zoom.
- `GridRaw` : dict[(x,y)] = code int (0 fermé, -1 drapeau, 1..8 num, 9 vide).
- `FrontierSlice` : sous-ensemble compact + densité/priorités + metadata viewport.
- `ActionBatch` : liste ordonnée d'actions sûres (flags/open) avec priorité et contexte.
- `PathfinderPlan` : liste d'actions à exécuter (click/flag/guess) envoyée par s5 vers s6.
- `SessionContext` : enrichi avec `historical_canvas_path` pour overlays historiques.

## 5. Précisions clés V2

- **Vision neutre** : plus de calcul topologique dans vision, délégué à storage/state_analyzer
- **Storage source de vérité** : gestion centralisée des sets avec invariants stricts
- **FocusActualizer stateless** : séparé de la logique de stockage
- **Frontier depuis storage** : solver consomme la frontière, ne la calcule plus
- **Recalcul incrémental** : performance optimisée via mise à jour partielle des sets
- **Importance de l'ordre** : cells update avant recalculate sets pour cohérence

### Invariants Storage
- Cohérence solver_status/focus levels :
  - ACTIVE → focus_level_active in {TO_REDUCE, REDUCED}, focus_level_frontier = None
  - FRONTIER → focus_level_frontier in {TO_PROCESS, PROCESSED}, focus_level_active = None
  - Others → focus levels = None
- Cohérence logical_state/number_value :
  - OPEN_NUMBER → number_value obligatoire (1..8)
  - Other → number_value = None

## 6. SessionContext enrichi

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
    historical_canvas_path: Optional[str] = None  # Nouveau V2
```

## 7. Avantages de l'architecture V2

1. **Séparation claire** : chaque module a une responsabilité unique
2. **Pas de doublons** : storage est la source de vérité pour les sets
3. **Extensible** : focus_actualizer peut être enrichi indépendamment
4. **Testable** : chaque module peut être testé isolément
5. **Performance** : recalcul incrémental des sets, pas de calculs redondants
6. **Stateless** : FocusActualizer sans état, plus facile à maintenir

## 8. Points d'attention

- La frontière est reconstruite à chaque passe (délai d'une itération après actions solver)
- `frontier_add`/`frontier_remove` vides dans compute_solver_update (géré par storage)
- Focus levels doivent être initialisés lors des promotions dans StateAnalyzer
- Ordre critique dans storage : update cells → recalculate sets

## 9. Migration Extension

- Préparation Native Messaging : l'extension envoie `capture` / `solve` / `act` au backend Python via JSON.
- Option translation Rust/C++ → WebAssembly pour embarquer la logique côté extension. Décision à prendre après stabilisation complète.
- Overlays conservés (PNG/JSON) pour être ré-exploités dans une UI pédagogique.

## 10. Roadmap (rappel)

Itération 0 : nettoyage + création arborescence s0→s6 + `main_simple.py`.
Itération 1 : s0_interface refactor.
Itération 2 : s1_capture (canvas toDataURL).
Itération 3 : s2_vision (sampler + calibration + debug).
Itération 4 : s3_storage (grille sparse + sets + invariants).
Itération 5 : s4_solver.
Itération 6 : s5_actionplanner.
Itération 7 : s6_action.
Itération 8 : Extension-ready (interfaces isolées, proto Native Messaging).

## 11. Arborescence cible (référence)

```
src/
├─ app/                      # points d'entrée (cli / scripts)
├─ services/                 # orchestrateurs (session, boucle…)
└─ lib/
    ├─ s0_interface/
    │  ├─ facade.py / controller.py           # portes d'entrée
    │  ├─ s01_*, s02_* …                      # toute la logique
    │  └─ __init__.py
    ├─ s1_capture/
    │  ├─ facade.py / controller.py
    │  ├─ s11_*, s12_* …
    │  └─ __init__.py
    ├─ s2_vision/
    │  ├─ facade.py / controller.py
    │  ├─ s21_*, s22_* …
    │  ├─ __init__.py
    │  └─ debug/
    │       ├─ overlay_renderer.py
    │       └─ json_exporter.py
    ├─ s3_storage/
    │  ├─ facade.py / controller.py (aucune logique)
    │  ├─ s30_session_context.py
    │  ├─ s31_grid_store.py, s32_set_manager.py, …
    │  ├─ serializers.py
    │  └─ __init__.py
    ├─ s4_solver/
    │  ├─ facade.py / controller.py
    │  ├─ s40_states_analyzer/
    │  │  ├─ state_analyzer.py          # NOUVEAU V2
    │  │  ├─ frontier_view_factory.py   # NOUVEAU V2
    │  │  └─ grid_classifier.py
    │  ├─ s45_focus_actualizer.py       # NOUVEAU V2
    │  ├─ s49_optimized_solver.py
    │  └─ __init__.py
    ├─ s5_actionplanner/
    │  ├─ facade.py / controller.py
    │  ├─ s51_*, s52_* …
    │  └─ __init__.py
    ├─ s6_action/
    │  ├─ facade.py / controller.py
    │  ├─ s61_*, s62_* …
    │  └─ __init__.py
    └─ main_simple.py                 # boucle while simple (entry prototype)
```

## 12. Règles d'implémentation

- Chaque dossier `src/sX_*` contient `interface.py` décrivant son contrat officiel.
- Tests unitaires par couche, référencés dans `tests/` avec README spécifique.
- Journaliser les décisions majeures dans `SPECS/DEVELOPMENT_JOURNAL.md` après chaque itération.
- Aucune duplication documentaire : `doc/` = résumés, `SPECS/` = référence technique.

### 12.1 Conventions de nommage
- `facade.py` et `controller.py` sont uniquement des points d'entrée : aucune logique métier.
- Toute logique d'une couche vit dans des fichiers préfixés `sXY_` (ex. `s31_grid_store.py`, `s45_focus_actualizer.py`).
- Les modules de debug/debugging portent des noms explicites (`debug/overlay_renderer.py`, etc.).
- Les tests suivent la convention `tests/test_<couche>_*.py`.

## 13. Fichiers modifiés/créés V2

### Nouveaux
- `src/lib/s4_solver/s45_focus_actualizer.py`
- `src/lib/s4_solver/s40_states_analyzer/state_analyzer.py`
- `src/lib/s4_solver/s40_states_analyzer/frontier_view_factory.py`

### Modifiés
- `src/lib/s3_storage/s31_grid_store.py` : ajout `_recalculate_sets()`
- `src/lib/s3_storage/s32_set_manager.py` : ajout méthodes individuelles et purge TO_VISUALIZE
- `src/lib/s2_vision/s23_vision_to_storage.py` : simplifié `matches_to_upsert()`
- `src/lib/s4_solver/s49_optimized_solver.py` : suppression `compute_frontier_from_cells()`
- `src/lib/s4_solver/controller.py` : utilisation frontier depuis storage
- `src/lib/s3_storage/s30_session_context.py` : ajout `historical_canvas_path`
- `src/services/s5_game_loop_service.py` : intégration StateAnalyzer

Cette architecture V2 est maintenant conforme aux SPECS archivées, complètement implémentée et fonctionnelle.
