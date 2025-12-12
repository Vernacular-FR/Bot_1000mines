---
description: Spécification technique de la couche s3_storage (stockage à trois sets)
---

# S03 STORAGE – Spécification technique

Couche de stockage passive pour le bot Minesweeper, basée sur une grille sparse et trois sets de coordonnées (revealed/unresolved/frontier).

## 1. Architecture

### 1.1 Vue d'ensemble
```
┌─────────────────┐     ┌─────────────────┐    ┌─────────────────┐
│   Vision (s2)   │───▶│   Storage (s3)  │◀───│   Solver (s4)   │
│                 │     │                 │    │                 │
│ • revealed_add  │     │ • GridStore     │    │ • frontier_add  │
│ • unresolved_add│     │ • SetManager    │    │ • unresolved_rm │
└─────────────────┘     └─────────────────┘    └─────────────────┘
```

### 1.2 Composants
- **GridStore** (`s31_grid_store.py`) : Dictionnaire sparse `{(x,y) → GridCell}`
- **SetManager** (`s32_set_manager.py`) : Trois sets de coordonnées
- **Controller** (`controller.py`) : Façade API vers les deux composants
- **Facade** (`facade.py`) : Dataclasses et protocoles

### 1.3 Schéma mémoire
```
┌──────────────────────────────────────────────────────┐
│                    StorageController                 │
│  ┌──────────────────────┐    ┌────────────────────┐  │
│  │      GridStore       │    │    SetManager      │  │
│  │  cells: dict[(x,y)]  │    │  ┌──────────────┐  │  │
│  │   ┌──────────────┐   │    │  │ revealed_set │◀┘  │
│  │   │ GridCell     │   │    │  ├──────────────┤    │
│  │   │ state/value  │   │    │  │ unresolved_set│◀──┘
│  │   │ solver_status│   │    │  ├──────────────┤     │
│  │   └──────────────┘   │    │  │ frontier_set │◀──┐ │
│  └──────────────────────┘    │  └──────────────┘   │ │
│        ▲   ▲   ▲             └──────────────────┘  │ │
│        │   │   │                  ▲               │ │
│  cells update  │                  │ apply_set_updates
│        │   │   │                  │ (revealed/unresolved/frontier)
└────────┴───┴───┴──────────────────┴─────────────────┘
         │   │
         │   └── GridCell = {x,y,state,value,solver_status,source}
         └───── Sets ne stockent que les coordonnées (tuples)
```
*Lecture des données :* `get_cells(bounds)` interroge **GridStore** pour récupérer les `GridCell`.  
*Lecture des ensembles :* `get_revealed()`, `get_unresolved()`, `get_frontier()` retournent des copies des trois sets gérés par **SetManager**.

### 1.3 Trois sets
- **revealed_set** : Toutes les cellules déjà découvertes (optimisation Vision)
- **unresolved_set** : Cellules révélées en attente de traitement solver
- **frontier_set** : Cellules fermées adjacentes aux révélées (frontière analytique)

## 2. API Contract

### 2.1 StorageUpsert
```python
@dataclass
class StorageUpsert:
    cells: dict[tuple[int, int], GridCell]
    revealed_add: set[tuple[int, int]] = field(default_factory=set)      # Vision only
    unresolved_add: set[tuple[int, int]] = field(default_factory=set)    # Vision only  
    unresolved_remove: set[tuple[int, int]] = field(default_factory=set) # Solver only
    frontier_add: set[tuple[int, int]] = field(default_factory=set)      # Solver only
    frontier_remove: set[tuple[int, int]] = field(default_factory=set)   # Solver only
```

### 2.2 StorageControllerApi
```python
class StorageControllerApi(Protocol):
    def upsert(self, data: StorageUpsert) -> None: ...
    def get_frontier(self) -> FrontierSlice: ...
    def get_revealed(self) -> set[tuple[int, int]]: ...
    def get_unresolved(self) -> set[tuple[int, int]]: ...
    def get_cells(self, bounds: tuple[int, int, int, int]) -> dict[tuple[int, int], GridCell]: ...
    def export_json(self, viewport_bounds: tuple[int, int, int, int]) -> dict: ...
```

## 3. Flux de données

### 3.1 Cycle typique
1. **Vision → Storage** : `upsert()` avec `revealed_add` + `unresolved_add`
2. **Solver → Storage** : `get_unresolved()` pour récupérer les cellules à traiter
3. **Solver → Storage** : `upsert()` avec `unresolved_remove` + `frontier_add/remove`
4. **Storage → Solver** : `get_frontier()` pour la prochaine itération

### 3.2 Séquence d'opérations
```
Vision découvre (1,2) et (2,2):
  revealed_add = {(1,2), (2,2)}
  unresolved_add = {(1,2), (2,2)}
  → Storage upsert

Solver traite (1,2):
  unresolved_remove = {(1,2)}
  frontier_add = {(1,3), (2,3)}  # voisins fermés
  → Storage upsert
```

## 4. Implémentation

### 4.1 SetManager
Gère les trois sets avec mise à jour atomique :
```python
def apply_set_updates(self, *, revealed_add, unresolved_add, 
                     unresolved_remove, frontier_add, frontier_remove):
    self._revealed_set.update(revealed_add)
    self._unresolved_set.update(unresolved_add)
    self._unresolved_set.difference_update(unresolved_remove)
    self._frontier_set.update(frontier_add)
    self._frontier_set.difference_update(frontier_remove)
```

### 4.2 GridStore
Délègue les opérations de sets à SetManager :
```python
def apply_upsert(self, data: StorageUpsert):
    self._cells.update(data.cells)
    self._sets.apply_set_updates(...)
```

## 5. Invariants et validation

### 5.1 Contraintes à maintenir
- `unresolved_set ⊆ revealed_set` (toutes les unresolved sont révélées)
- `frontier_set ∩ revealed_set = ∅` (frontier ne contient que des fermées)
- `frontier_set ⊆ voisins(revealed_set)` (frontier adjacent aux révélées)

### 5.2 Validation建议
Ajouter des assertions dans `apply_set_updates()` pour vérifier les invariants après chaque mise à jour.

## 6. Pièges courants

### 6.1 Erreurs à éviter
- **Vision calcule frontier_add** : ❌ Seul le Solver doit calculer la frontière
- **Solver modifie revealed_set** : ❌ Seul Vision ajoute des révélées
- **Sets partagés par référence** : ❌ Les getters retournent des copies

### 6.2 Bonnes pratiques
- Toujours utiliser les champs `*_add`/`*_remove` (pas de modification directe)
- Valider que `unresolved_add` ⊆ `revealed_add` côté Vision
- Vérifier la cohérence des `frontier_add` avec les cellules révélées

## 7. Intégration exemples

### 7.1 Batch Vision typique
```python
vision_batch = StorageUpsert(
    cells={(x,y): GridCell(x=x, y=y, state=OPEN_NUMBER, value=1)},
    revealed_add={(x,y)},
    unresolved_add={(x,y)},
    # frontier_* laissés vides (Vision ne calcule pas)
)
storage.upsert(vision_batch)
```

### 7.2 Mise à jour Solver typique
```python
solver_update = StorageUpsert(
    cells={},  # pas de nouvelles cellules
    revealed_add=set(),
    unresolved_add=set(),
    unresolved_remove={processed_coords},
    frontier_add={new_frontier_coords},
    frontier_remove={obsolete_frontier_coords}
)
storage.upsert(solver_update)
```

## 8. Performance

- **Objectif** : < 2ms par batch upsert
- **Taille typique** : Quelques milliers de coordonnées par set
- **Optimisation** : Sets Python + dict sparse = O(1) pour les opérations courantes

## 9. Références

- `PLAN_S3_STORAGE.md` : Plan d'implémentation détaillé
- `ARCHITECTURE.md` : Architecture globale du bot
- Tests : `tests/test_s3_storage_*.py` (à créer)

---

*Storage est une couche passive : elle stocke, ne calcule pas. La logique analytique appartient au Solver.*