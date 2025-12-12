---
description: Analyse et plan d’implémentation s3_storage (archive + frontière)
---

# PLAN S3 STORAGE – Analyse & feuille de route

Document de cadrage qui synthétise les exigences de `PLAN_SIMPLIFICATION radicale.md` et `SYNTHESE_pipeline_refonte.md` pour la couche s3. Il restera la référence tant que l’implémentation n’est pas finalisée.

## 1. Mission
- Maintenir **une seule représentation de vérité** : dictionnaire sparse `{(x, y) → GridCell}` non borné + trois sets de coordonnées, sans double base.
- Fournir les **structures nécessaires** à s4 (revealed_set, unresolved_set, frontier_set) pour le workflow solver.
- Garantir qu’aucune donnée n’est perdue : la grille globale reste exhaustive ; les sets stockent uniquement les coordonnées pour optimiser le traitement.
- **Export JSON** pour compatibilité WebExtension (pas de formats binaires propriétaires, focus sur la zone visible + marge).
- **Stockage passif** : Vision pousse revealed+unresolved, Solver calcule frontier_add/remove, storage ne fait que stocker.
- **Set revealed** : coordonnées des cellules déjà connues (optimisation Vision, évite re-scan).
- **Set unresolved** : cellules révélées mais pas encore traitées par le solver (UNRESOLVED→TO_PROCESS→RESOLVED géré par solver).
- **Set frontier** : cellules fermées adjacentes aux révélées (frontière analytique sur laquelle le solver travaille).

## 2. Architecture cible
```
s3_storage/
├─ facade.py           # dataclasses (GridCell, FrontierSlice, StorageUpsert)
├─ controller.py       # façade vers GridStore + SetManager
├─ s31_grid_store.py    # grille sparse dict
├─ s32_set_manager.py   # gestion des trois sets (revealed/unresolved/frontier)
└─ __init__.py
```

### 2.1 Structures principales
- **GridCell**
  - `(x, y)`, `state` (enum : CLOSED, OPEN_NUMBER, OPEN_EMPTY, FLAG, UNKNOWN)
  - `value` (0..8 pour les chiffres), `source` (vision / solver), `updated_at`.
- **Grille globale (dict sparse)**
  - `cells: dict[tuple[int, int], GridCell]`
  - Non bornée : aucun offset ni redimensionnement, stockage uniquement des cases connues.
  - Permet d’extraire à la volée des “patchs” denses (ex : 200×200) si besoin pour du NumPy local.
- **Set revealed**
  - `revealed_coords: set[tuple[int, int]]` pour optimisation Vision (évite re-scan cases connues).
- **Set unresolved**
  - `unresolved_coords: set[tuple[int, int]]` des cellules révélées en attente de traitement solver.
- **Set frontier**
  - `frontier_coords: set[tuple[int, int]]` des cellules fermées adjacentes aux révélées (frontière analytique).

## 3. API (facade)
```python
@dataclass
class StorageUpsert:
    cells: dict[tuple[int, int], GridCell]
    revealed_add: set[tuple[int, int]] = field(default_factory=set)
    unresolved_add: set[tuple[int, int]] = field(default_factory=set)
    unresolved_remove: set[tuple[int, int]] = field(default_factory=set)
    frontier_add: set[tuple[int, int]] = field(default_factory=set)
    frontier_remove: set[tuple[int, int]] = field(default_factory=set)

@dataclass
class FrontierSlice:
    coords: set[tuple[int, int]]          # coordonnées frontière actuelles

class StorageControllerApi(Protocol):
    def upsert(self, data: StorageUpsert) -> None: ...
    def get_frontier(self) -> FrontierSlice: ...
    def get_revealed(self) -> set[tuple[int, int]]: ...
    def get_unresolved(self) -> set[tuple[int, int]]: ...
    def get_cells(self, bounds: tuple[int, int, int, int]) -> dict[tuple[int, int], GridCell]: ...
    def export_json(self, viewport_bounds: tuple[int, int, int, int]) -> dict: ...
```

### 3.1 Gestion incrémentale des sets
- Les trois sets (`revealed`, `unresolved`, `frontier`) sont gérés incrémentalement via `*_add`/`*_remove`.
- Vision ajoute les nouvelles cellules révélées dans `revealed_add` et `unresolved_add` (pas de `frontier_add`).
- Solver met à jour `unresolved_remove` (cellules traitées) et `frontier_add/remove` (propagation analytique).
- **Note** : `frontier_add/remove` sont utilisés uniquement par Solver, jamais par Vision.
- Pas de recalcul complet à chaque itération : seules les zones impactées par le batch sont touchées.

## 4. Flux de données (séquentiel)
1. **Vision (s2)** → `StorageController.upsert(batch)` : applique toutes les révélations en une passe, met à jour `cells`, `revealed_add` et `unresolved_add` (pas de `frontier_add`).
2. **Solver (s4)** → `get_unresolved()` : récupère les cellules UNRESOLVED, applique filtre (exclure résolues d’elles-mêmes), puis motifs sur les TO_PROCESS.
3. **Solver → Storage** : met à jour `unresolved_remove` (cellules traitées) et `frontier_add/remove` (propagation analytique calculée depuis les TO_PROCESS).
4. **Solver → s5_actionplanner** : retourne actions brutes (clics/drapeaux) pour planification.
5. **Action (s6)** : exécute séquentiellement, valide les mises à jour de frontière, puis déclenche nouvelle capture → retour à l'étape 1.

## 5. Plan d’implémentation
1. **Phase 1 – Infrastructure** 
   - Définir `facade.py` (GridCell, StorageUpsert, FrontierSlice).
   - Implémenter `s31_grid_store.py` (dict sparse) + `s32_set_manager.py` (trois sets).
   - Implémenter `controller.py` comme façade pure vers GridStore + SetManager.
2. **Phase 2 – Intégration vision/solver** 
   - Vision pousse des batches (révélations + revealed_add + unresolved_add, **sans frontier_add**).
   - Solver consomme `get_unresolved()`, puis renvoie les mises à jour (unresolved_remove, frontier_add/remove calculés).
3. **Phase 3 – Solver coordination** 
   - Solver gère UNRESOLVED→TO_PROCESS→RESOLVED et met à jour la frontière analytique.
   - Alimenter s5 avec les actions sûres pour ses séquences viewport.
4. **Phase 4 – Export JSON & debug** 
   - `export_json(viewport_bounds)` : série limitée à la zone visible + marge.
   - Pas de métriques dans storage (calculées par solver/actionplanner si besoin).
5. **Phase 5 – Extensions optionnelles** 
   - Snapshots persistants (`.npy`, HDF5, SQLite logs) si nécessaire, mais hors boucle solver.
   - Outils d’inspection/frontier pour vérifier les batches vision/solver.

## 6. Validation & KPIs
- Cohérence grille/sets (toutes les cases révélées sont dans revealed_set, toutes les UNRESOLVED dans unresolved_set, toutes les fermées adjacentes dans frontier_set).
- Temps de mise à jour après vision : objectif < 2 ms par capture.
- Taille sets : typiquement quelques milliers de cases (<10% de grille 100k cases).
- Tests unitaires : insertion d’une grille 3×3, propagation d’updates, vérification des trois sets.
- Tests réels : grilles de `temp/games/` et captures de `tests/set_screeshot/`.

## 7. Références
- `development/PLAN_SIMPLIFICATION radicale.md` – sections s3 et roadmap.
- `development/SYNTHESE_pipeline_refonte.md` – §4 Stockage & frontier management.
- `doc/PIPELINE.md` & `doc/SPECS/ARCHITECTURE.md` – description macro de la couche s3.

---

*Plan implémenté et aligné avec l'architecture à trois sets (revealed/unresolved/frontier). Storage est désormais passif, la logique analytique est déléguée au solver.*
