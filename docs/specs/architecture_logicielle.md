# Architecture Logicielle - Bot Minesweeper

> **Portée** : Couches applicatives et interfaces uniquement

---

## Couches Applicatives

### Interface (main.py)
- **Responsabilités** :
  - Affichage du menu utilisateur
  - Collecte des choix utilisateur
  - Lancement des scénarios
- **Interface** : `launch_scenario(scenario_id: int) → bool`

### Applicative (bot_1000mines.py)
- **Responsabilités** :
  - Orchestration des services métier
  - Gestion du workflow global
  - Coordination des étapes du jeu
- **Interface** :
  - `run_navigation_test() → bool`
  - `run_capture_test() → bool`
  - `run_analysis_test() → bool`
  - `run_solver_test() → bool`
  - `run_complete_game() → bool`

### Services (services/*.py)
- **Responsabilités** :
  - Orchestration des utilitaires techniques
  - Gestion des sessions de travail
  - Coordination des opérations complexes
- **Services principaux** :
  - **SessionSetupService** : Configuration et initialisation des sessions
  - **ZoneCaptureService** : Capture et préparation des zones de jeu
  - **OptimizedAnalysisService** : Analyse optimisée des grilles
  - **GameSolverService** : Résolution logique des puzzles
  - **ActionExecutorService** : Exécution des actions de jeu
  - **GameLoopService** : Orchestration complète des parties

---

## Interfaces des Services

### SessionSetupService
```python
class SessionSetupService:
    def __init__(self, driver, config: dict)
    def setup_session() → dict
    def get_driver() → WebDriver
    def cleanup() → bool
```

### ZoneCaptureService
```python
class ZoneCaptureService:
    def __init__(self, driver, paths: dict, game_id: str)
    def capture_window(filename: str = None, overlay_interface: bool = True) → dict
    def capture_game_zone_inside_interface(session_service, iteration_num: int) → dict
```

### OptimizedAnalysisService
```python
class OptimizedAnalysisService:
    def __init__(self, paths: dict)
    def analyze_from_path(image_path: str, zone_bounds: tuple = None) → dict
    def analyze_single_screenshot_optimized(screenshot_path: str, ...) → dict
    def build_cell_state_index(zone_bounds: tuple, with_metrics: bool = False) → dict | (dict, dict)
```

#### Pipeline incrémental (passes)
- **Pré-analyse**
  - Construction d’un `cell_state_index` en mémoire via GridDB pour disposer des états hérités (`known`, `unknown`, `unrevealed`, `empty`, `number_n`, `flag`).
  - Calcul des métriques `cells_total`, `cells_known`, `cells_skipped` afin d’alimenter les KPIs.
  - Filtrage initial donnant `candidate_cells`, `known_cells`, `truly_unknown_cells`.
- **Pass00 – `unrevealed_check`**
  - Scope : uniquement les cellules réellement inconnues (`truly_unknown_cells`).
  - Matching visuel ciblé (templates `unrevealed`) puis persistance immédiate dans GridDB + retrait des cells confirmées pour les passes suivantes.
- **Pass01 – `empty_refresh` (logique)**
  - Ne réalise plus de matching visuel : déduit les cellules `empty` en se basant sur la connectivité aux `unrevealed` détectées en Pass00.
  - Règle actuelle : toute cellule candidate *non adjacente* à un `unrevealed` est marquée `empty` avec confiance 1.0 (les cellules adjacentes forment la frontière potentielle de chiffres/décor).
  - Les résultats sont persistés immédiatement et retirés des passes suivantes.
- **Pass02 – `exploded_check` (templates mines)**
  - Matching visuel restreint à `exploded` pour identifier les mines déjà révélées (couleurs rouges).
  - Utilise un seuil dédié (`EXPLODED_MIN_CONFIDENCE`) et un mapping multi-templates (ex: `exploded.png`, `exploded_a.png`).
- **Pass03 – `cnn_refresh` (ou fallback `numbers_refresh`)**
  - Si le CNN est chargé (`best_model.pth` + `config.yaml`), les patches restants passent par `CNNCellClassifier` (`accept_threshold` par défaut, mais `number_X` acceptés dès 0.50, `exploded` conservé au seuil d’inférence).
  - Si le CNN est indisponible, fallback sur `numbers_refresh` (template matching `number_1..number_8`).
  - Les résultats sont écrits dans GridDB/TensorGrid puis utilisés par le solver.
- **Overlays & Diff**
  - Chaque passe peut générer son overlay (`passXX_name.png`) + un diff JSON listant les cellules dont l’état change.
  - Les métriques sont consolidées dans `pass_metrics` (input, matched, durée).

> **Logs clefs** : `[STATE]`, `[FILTER]`, `[PASS]`, `[INFO] Logical empty inference`.  
> **KPIs** : `cells_scanned`, `scan_ratio`, `tm_backend`, `tm_fallback_used`, `tm_shadow_divergent`.

### GameSolverService
```python
class GameSolverService:
    def __init__(self, paths: dict)
    def solve_from_db_path(db_path: str, image_path: str) → dict
    def convert_actions_to_game_actions(solve_result: dict) → list
```

### ActionExecutorService
```python
class ActionExecutorService:
    def __init__(self, coordinate_system, driver)
    def execute_batch(actions: list) → dict
    def execute_single_action(action) → bool
```

### GameLoopService
```python
class GameLoopService:
    def __init__(self, session_service, max_iterations: int = 100, ...)
    def run_game_loop() → GameResult
    def execute_single_pass(iteration_num: int = None) → dict
```

---

## Flux de Communication

### Flux Normal (Interface → Services → Utilitaires)
```
Interface
    ↓ (lance scénario)
Applicative
    ↓ (coordonne services)
Services métier
    ↓ (orchestrent utilitaires)
Utilitaires techniques
    ↓ (opérations élémentaires)
Résultats
```

### Flux d'Erreurs (remontée)
```
Utilitaires techniques
    ↑ (exceptions)
Services métier
    ↑ (wrapping + contexte)
Applicative
    ↑ (gestion + logging)
Interface
    ↑ (affichage utilisateur)
```

---

## Chaîne Vision → Tensor (Phase 3)

1. **Capture Patch (S1)**  
   `ZoneCaptureService` fournit pour chaque itération un `CapturePatch` contenant l’image découpée, ses bornes absolues et un `usable_mask` (zone réellement exploitable hors interface).

2. **SmartScan (S2)**  
   `SmartScanService.process_patches()` applique le template matching fixe, construit un `GridAnalysis` puis écrit directement dans TensorGrid via `_write_tensor_update`.  
   - Génère `codes`, `confidences`, `dirty_mask` et `frontier_mask` (cases non révélées adjacentes aux nombres).  
   - Publie les bornes modifiées dans `HintCache` pour le solver.

3. **TensorGrid & TraceRecorder (S3)**  
   `TensorGrid.update_region()` agrège les tenseurs (valeurs, confiance, âge, frontier_mask, dirty_mask) et expose les statistiques globales via `tensor_grid.stats()`.  
   `TraceRecorder.capture()` sauvegarde un snapshot complet (`values`, `confidence`, `frontier_mask`, etc.) avec les métadonnées de tick.

4. **KPIs Vision obligatoires**  
   SmartScan loggue et renvoie dans `metrics` :  
   - `cells_per_second` (débit traitement)  
   - `known_ratio` (ratio cellules connues TensorGrid)  
   - `frontier_cells` & `dirty_cells` (état du solver)  
   Ces mêmes valeurs sont routées dans TraceRecorder pour instrumentation offline.

5. **Compatibilité GridDB**  
   Tant que le solver legacy dépend de `grid_state_db.json`, SmartScan continue à mettre à jour la GridDB en miroir (même résumé, distribution des symboles) avant de flusher sur disque.

Ce pipeline garantit que chaque passe Vision produit immédiatement des tenseurs consommables par S4, tout en gardant des métriques de performance pour phase 3/4.

### Phase 4 — Solver Tensor-native

1. **Lecture directe TensorGrid**  
   `GameSolverService` récupère une vue ciblée (`get_solver_view(bounds)`) en fusionnant les dirty sets du `HintCache`. `GridState` & `GridAnalyzer` acceptent désormais un `tensor_view` (valeurs, confidence, frontier_mask, origin) ce qui évite la reconstruction intégrale depuis GridDB.

2. **Frontier hint**  
   `GridState` transporte un `frontier_hint` issu de `frontier_mask`. `Frontier` peut alors reconstituer les contraintes sans rescanner toute la grille. (Étape suivante : `tensor_frontier.py` pour segmenter directement depuis TensorGrid.)

3. **KPI Solver**  
   Chaque résolution loggue `frontier_cells`, `zones`, `components`, `dirty_sets_consumed`, `solve_duration` et pousse ces métriques dans TraceRecorder. Cela permet de profiler les itérations longues et d’alimenter les dashboards Phase 4/5.

4. **Compatibilité**  
   GridDB reste rempli en miroir (pour héritage/overlays), mais le solver consomme TensorGrid en priorité. HintCache assure la synchronisation Vision→Solver.

---

## Patterns Architecturaux

### Dependency Injection
- Tous les services reçoivent leurs dépendances en paramètres
- Interfaces explicites plutôt qu'implicites
- Testabilité améliorée

### Service Layer Pattern
- Services comme façade pour la logique métier
- Séparation claire orchestration / implémentation
- Interfaces stables malgré changements internes

### Result Pattern
- Toutes les méthodes retournent `Dict[str, Any]` avec clés standardisées
- Gestion uniforme des succès/échecs
- Métadonnées riches pour debugging

### Path Configuration
- Chemins injectés via paramètres `paths: dict`
- Centralisation de la configuration
- Flexibilité pour différents environnements
