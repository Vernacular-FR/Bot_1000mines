---
description: Analyse et plan d’implémentation s3_storage (archive + frontière)
---

# PLAN S3 STORAGE – Analyse & feuille de route

Document de cadrage qui synthétise les exigences de `PLAN_SIMPLIFICATION radicale.md` et `SYNTHESE_pipeline_refonte.md` pour la couche s3. Il restera la référence tant que l’implémentation n’est pas finalisée.

## 1. Mission
- Maintenir **une seule représentation de vérité** : dictionnaire sparse `{(x, y) → GridCell}` non borné + frontière compacte (set de coordonnées), sans double base.
- Fournir les **métriques** nécessaires à s5 (densité, attracteurs) et les structures nécessaires à s4 (contraintes locales à calculer côté solver).
- Garantir qu’aucune donnée n’est perdue : la grille globale reste exhaustive ; la frontière stocke uniquement les coordonnées à traiter pour accélérer la résolution.
- **Export JSON** pour compatibilité WebExtension (pas de formats binaires propriétaires, focus sur la zone visible + marge).
- **Mise à jour frontière** : uniquement par Vision (batch) et Actioner (validation Pathfinder), le solver reste en lecture seule.
- **Set revealed** : pour optimisation Vision, évite de re-scanner les cases déjà connues.
- **solver_status** : géré par Solver (UNRESOLVED/TO_PROCESS/RESOLVED), storage passif.

## 2. Architecture cible
```
s3_storage/
├─ facade.py           # dataclasses (GridCell, FrontierSlice, StorageRequest…)
├─ controller.py       # archive + frontière + synchronisation
├─ frontier.py         # helpers calcul densité, extraction composantes
├─ serializers.py      # JSONL / SQLite (optionnel, phase 2)
└─ debug/
    └─ inspectors.py   # impression / overlays / logs
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
- **Frontière**
  - `frontier_coords: set[tuple[int, int]]` contenant uniquement les coordonnées des cellules TO_PROCESS.
  - Métadonnées calculées à la demande via `frontier_metrics` (densité de drapeaux, actions en attente, attracteur).
  - Les données complètes restent dans `cells`; la frontière manipule des tuples à ajouter/retirer (vision & solver).

## 3. API (facade)
```python
@dataclass
class StorageUpsert:
    cells: dict[tuple[int, int], GridCell]
    revealed_add: set[tuple[int, int]] = field(default_factory=set)
    frontier_add: set[tuple[int, int]] = field(default_factory=set)
    frontier_remove: set[tuple[int, int]] = field(default_factory=set)

@dataclass
class FrontierSlice:
    coords: set[tuple[int, int]]          # coordonnées TO_PROCESS actuelles
    metrics: FrontierMetrics              # densité, attracteur, bbox

class StorageControllerApi(Protocol):
    def upsert(self, data: StorageUpsert) -> None: ...
    def get_frontier(self) -> FrontierSlice: ...
    def get_revealed(self) -> set[tuple[int, int]]: ...
    def mark_processed(self, positions: set[tuple[int, int]]) -> None: ...
    def get_cells(self, bounds: tuple[int, int, int, int]) -> dict[tuple[int, int], GridCell]: ...
    def export_json(self, viewport_bounds: tuple[int, int, int, int]) -> dict: ...
```

### 3.1 Gestion incrémentale de la frontière
- La frontière est un simple set de coordonnées manipulé via `frontier_add/frontier_remove`.
- Vision ajoute toutes les cellules nouvellement visibles + leurs voisins fermés dans un **batch unique**.
- Actioner peut retirer des coordonnées une fois les actions appliquées (validation des mises à jour anticipées par Pathfinder).
- Pas de recalcul complet à chaque itération : seules les zones impactées par le batch sont touchées.

## 4. Flux de données (séquentiel)
1. **Vision (s2)** → `StorageController.upsert(batch)` : applique toutes les révélations en une passe, met à jour `cells` et injecte `frontier_add/remove`.
2. **Solver (s4)** → `get_frontier()` : récupère le set actuel + métriques, reconstruit ses composantes en interne, retourne **uniquement les actions**.
3. **Solver → s5_pathfinder** : retourne actions brutes (clics/drapeaux) pour planification.
4. **Pathfinder (s5)** :
   - Calcule les mises à jour anticipées de la frontière en fonction des actions planifiées.
   - Ordonne les actions + frontière_anticipée puis délègue à s6.
5. **Action (s6)** : exécute séquentiellement, valide les mises à jour de frontière, puis déclenche nouvelle capture → retour à l'étape 1.

## 5. Plan d’implémentation
1. **Phase 1 – Infrastructure**
   - Définir `facade.py` (GridCell, StorageUpsert, FrontierSlice, FrontierMetrics).
   - Implémenter `controller.py` minimal : dict sparse + set frontier (ajout/retrait incrémental).
2. **Phase 2 – Intégration vision/solver**
   - Vision pousse des batches (révélations + frontier_add/remove).
   - Solver consomme `FrontierSlice`, puis renvoie les coordonnées à retirer une fois les actions terminées.
3. **Phase 3 – Pathfinder coordination**
   - Calculer attractivité uniquement sur les coordonnées touchées (delta metrics).
   - Alimenter s5 avec la frontière attendue pour ses séquences viewport.
4. **Phase 4 – Export JSON & debug**
   - `export_json(viewport_bounds)` : série limitée à la zone visible + marge pour l’extension.
   - Overlays/debug sur les zones locales (pas besoin d’exporter toute la grille).
5. **Phase 5 – Extensions optionnelles**
   - Snapshots persistants (`.npy`, HDF5, SQLite logs) si nécessaire, mais hors boucle solver.
   - Outils d’inspection/frontier pour vérifier les batches vision/solver.

## 6. Validation & KPIs
- Cohérence grille/frontière (toutes les cases fermées de la frontière existent dans la grille).
- Temps de mise à jour après vision : objectif < 2 ms par capture.
- Taille frontière : typiquement quelques milliers de cases (<10% de grille 100k cases).
- Tests unitaires : insertion d’une grille 3×3, propagation d’updates, vérification frontier.
- Tests réels : grilles de `temp/games/` et captures de `tests/set_screeshot/`.

## 7. Références
- `development/PLAN_SIMPLIFICATION radicale.md` – sections s3 et roadmap.
- `development/SYNTHESE_pipeline_refonte.md` – §4 Stockage & frontier management.
- `doc/PIPELINE.md` & `doc/SPECS/ARCHITECTURE.md` – description macro de la couche s3.

---

*Ce plan sera complété après stabilisation des API s2 (vision) et des besoins solver/pathfinder.*
