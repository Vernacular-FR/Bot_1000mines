# Architecture Alternative A : Modules Purs Découplés

## Type d'Architecture

**"Modular Pipeline Architecture"** (inspirée Clean Architecture / Ports & Adapters)

Principes fondamentaux :
- **Séparation des responsabilités** : 1 module = 1 responsabilité claire
- **Contrats explicites** : chaque module définit son Input/Output
- **Pipeline unidirectionnel** : pas de dépendances circulaires
- **Stateless** : les modules ne gardent pas d'état entre les appels

---

## Structure Cible

```
src/
├── lib/
│   ├── s0_browser/           # Gestion navigateur Selenium
│   │   ├── __init__.py
│   │   ├── browser.py        # start, stop, execute_js, get_driver
│   │   └── types.py          # BrowserConfig, BrowserState
│   │
│   ├── s0_coordinates/       # Conversion coordonnées grille ↔ écran
│   │   ├── __init__.py
│   │   ├── converter.py      # grid_to_screen, screen_to_grid
│   │   ├── viewport.py       # viewport mapping, bounds
│   │   └── types.py          # Coord, ScreenPoint, GridBounds
│   │
│   ├── s1_capture/           # Capture canvas
│   │   ├── __init__.py
│   │   ├── capture.py        # capture_canvas(driver) -> bytes
│   │   └── types.py          # CaptureResult
│   │
│   ├── s2_vision/            # Reconnaissance visuelle
│   │   ├── __init__.py
│   │   ├── vision.py         # analyze(image) -> VisionResult
│   │   ├── matcher.py        # template matching
│   │   ├── templates/        # templates images
│   │   └── types.py          # VisionResult, CellMatch
│   │
│   ├── s3_storage/           # État du jeu (source de vérité)
│   │   ├── __init__.py
│   │   ├── storage.py        # StorageController
│   │   ├── grid.py           # GridStorage
│   │   └── types.py          # GridCell, GameState
│   │
│   ├── s4_solver/            # Résolution (reducer + CSP)
│   │   ├── __init__.py
│   │   ├── solver.py         # solve(SolverInput) -> SolverOutput
│   │   ├── reducer.py        # réduction par contraintes simples
│   │   ├── csp.py            # CSP solver
│   │   ├── state_manager.py  # gestion état solver (frontier, active)
│   │   └── types.py          # SolverInput, SolverOutput, SolverAction
│   │
│   ├── s5_planner/           # Planification actions (module métier)
│   │   ├── __init__.py
│   │   ├── planner.py        # plan(actions, grid) -> ExecutionPlan
│   │   ├── optimizer.py      # optimisation ordre/regroupement
│   │   └── types.py          # ExecutionPlan, PlannedAction
│   │
│   ├── s6_executor/          # Exécution actions
│   │   ├── __init__.py
│   │   ├── executor.py       # execute(plan, driver) -> ExecutionResult
│   │   └── types.py          # ExecutionResult
│   │
│   └── s7_debug/             # Debug et overlays
│       ├── __init__.py
│       ├── overlays.py       # génération overlays visuels
│       └── logger.py         # logging structuré
│
├── services/
│   ├── session_service.py    # Init/cleanup session (browser, storage)
│   └── game_loop.py          # Pipeline principal
│
├── config.py                 # Configuration globale
└── main.py                   # Point d'entrée
```

---

## Contrats I/O par Module

### s0_browser
```python
# Input
@dataclass
class BrowserConfig:
    headless: bool = False
    url: str = "https://1000mines.com"

# Output
class BrowserHandle:
    driver: WebDriver
    def execute_js(self, script: str) -> Any: ...
    def close(self) -> None: ...

# API
def start_browser(config: BrowserConfig) -> BrowserHandle
def stop_browser(handle: BrowserHandle) -> None
```

### s0_coordinates
```python
# Input/Output types
@dataclass
class Coord:
    row: int
    col: int

@dataclass
class ScreenPoint:
    x: int
    y: int

@dataclass
class GridBounds:
    top_left: Coord
    bottom_right: Coord

# API
def grid_to_screen(coord: Coord, canvas_info: CanvasInfo) -> ScreenPoint
def screen_to_grid(point: ScreenPoint, canvas_info: CanvasInfo) -> Coord
def get_visible_bounds(viewport: Viewport) -> GridBounds
```

### s1_capture
```python
# Output
@dataclass
class CaptureResult:
    image: bytes
    timestamp: float
    canvas_rect: Rect

# API
def capture_canvas(driver: WebDriver) -> CaptureResult
```

### s2_vision
```python
# Input
@dataclass
class VisionInput:
    image: bytes
    bounds: GridBounds

# Output
@dataclass
class CellMatch:
    coord: Coord
    value: int  # 0-8, -1=mine, -2=unknown, -3=flag
    confidence: float

@dataclass
class VisionResult:
    matches: List[CellMatch]
    timestamp: float

# API
def analyze(input: VisionInput) -> VisionResult
```

### s3_storage
```python
# Types
@dataclass
class GridCell:
    coord: Coord
    value: int
    status: CellStatus  # UNKNOWN, REVEALED, FLAGGED

# API
def get_snapshot(bounds: GridBounds) -> Dict[Coord, GridCell]
def apply_upsert(upsert: StorageUpsert) -> None
def get_frontier() -> Set[Coord]
def get_active_set() -> Set[Coord]
```

### s4_solver
```python
# Input
@dataclass
class SolverInput:
    cells: Dict[Coord, GridCell]
    frontier: Set[Coord]
    active_set: Set[Coord]

# Output
@dataclass
class SolverAction:
    coord: Coord
    action: ActionType  # CLICK, FLAG, GUESS
    confidence: float

@dataclass
class SolverOutput:
    actions: List[SolverAction]
    upsert: StorageUpsert
    metadata: Dict[str, Any]

# API
def solve(input: SolverInput) -> SolverOutput
```

### s5_planner
```python
# Input
@dataclass
class PlannerInput:
    actions: List[SolverAction]
    grid_bounds: GridBounds
    viewport: Viewport

# Output
@dataclass
class PlannedAction:
    coord: Coord
    action: ActionType
    screen_point: ScreenPoint
    priority: int

@dataclass
class ExecutionPlan:
    actions: List[PlannedAction]
    estimated_time: float

# API
def plan(input: PlannerInput) -> ExecutionPlan
```

### s6_executor
```python
# Input
@dataclass
class ExecutorInput:
    plan: ExecutionPlan
    driver: WebDriver

# Output
@dataclass
class ExecutionResult:
    success: bool
    executed_count: int
    errors: List[str]
    duration: float

# API
def execute(input: ExecutorInput) -> ExecutionResult
```

---

## Pipeline Principal

```python
# game_loop.py
def run_iteration(browser: BrowserHandle, storage: Storage) -> IterationResult:
    # 1. Capture
    capture = s1_capture.capture_canvas(browser.driver)
    
    # 2. Vision
    bounds = s0_coordinates.get_visible_bounds(viewport)
    vision = s2_vision.analyze(VisionInput(capture.image, bounds))
    
    # 3. Storage update
    storage.apply_vision_result(vision)
    
    # 4. Solver
    solver_input = SolverInput(
        cells=storage.get_snapshot(bounds),
        frontier=storage.get_frontier(),
        active_set=storage.get_active_set()
    )
    solver_output = s4_solver.solve(solver_input)
    storage.apply_upsert(solver_output.upsert)
    
    # 5. Planner
    plan = s5_planner.plan(PlannerInput(
        actions=solver_output.actions,
        grid_bounds=bounds,
        viewport=viewport
    ))
    
    # 6. Executor
    result = s6_executor.execute(ExecutorInput(plan, browser.driver))
    
    return IterationResult(
        actions_executed=result.executed_count,
        success=result.success
    )
```

---

## Migration depuis Structure Actuelle

| Actuel | Cible A | Action |
|--------|---------|--------|
| `s0_interface/s00_browser_manager.py` | `s0_browser/browser.py` | Extraire logique browser |
| `s0_interface/s03_Coordonate_system.py` | `s0_coordinates/converter.py` | Extraire conversion |
| `s0_interface/s04_viewport_mapper.py` | `s0_coordinates/viewport.py` | Extraire viewport |
| `s0_interface/controller.py` | Supprimer | Logique → services |
| `s1_capture/*` | `s1_capture/capture.py` | Simplifier |
| `s2_vision/*` | `s2_vision/vision.py` + `matcher.py` | Simplifier (40→3 fichiers) |
| `s4_solver/s40_states_*` | `s4_solver/state_manager.py` | Fusionner |
| `s4_solver/s42_csp_solver/*` | `s4_solver/csp.py` | Simplifier |
| `s4_solver/s49_optimized_solver.py` | `s4_solver/reducer.py` | Renommer |
| `s5_actionplanner/*` | `s5_planner/*` | Renommer + enrichir |
| `s6_action/*` | `s6_executor/*` | Renommer |
| `services/*` (8 fichiers) | `services/` (2 fichiers) | Fusionner |

---

## Ordre de Refactoring

1. **s0_browser** + **s0_coordinates** (base)
2. **s1_capture** (simple)
3. **s2_vision** (complexe mais isolé)
4. **s3_storage** (minimal)
5. **s4_solver** (cœur logique)
6. **s5_planner** (module métier)
7. **s6_executor** (simple)
8. **s7_debug** (optionnel)
9. **services/** (orchestration)
10. **Validation pipeline**
