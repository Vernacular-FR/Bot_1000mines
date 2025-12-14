---
description: Feuille de route s4_solver (PatternEngine + LocalSolver)
---

# PLAN S4 SOLVER – Synthèse & objectifs

Document de travail qui synthétise les exigences du **PLAN DE SIMPLIFICATION RADICALE** et de **SYNTHESE_pipeline_refonte.md** pour la couche s4. Il servira de référence tant que l’implémentation n’est pas finalisée.

## 1. Mission
- Transformer la frontière analytique (frontier_set) de s3 en **actions sûres** (clics, drapeaux) sans jamais modifier la frontière elle-même.
- Consommer les cellules enrichies (`raw_state`, `logical_state`, `number_value`, `solver_status`, `action_status`) et maintenir les transitions **JUST_REVEALED → ACTIVE/FRONTIER → SOLVED**.
- Calculer lui-même les composantes connexes depuis `unresolved_set` (pas de pré-groupage) et marquer les cellules FRONTIER/ACTIVE concernées en `to_process` / `processed`.
- Retourner **uniquement les actions** à s5_actionplanner, PAS de mise à jour directe de storage (les updates frontier/unresolved passent par StorageUpsert).
- Garder la frontière en lecture seule : c'est à Vision et Actioner de la maintenir.
- Utiliser **NumPy** en interne pour efficacité, supporter **export JSON** pour compatibilité WebExtension.

## 2. Découpage prévu
```
s4_solver/
├─ s40_grid_analyzer/          # snapshot grille + statuts + vues
│   ├─ grid_classifier.py      # JUST_REVEALED → ACTIVE/FRONTIER/SOLVED
│   └─ grid_extractor.py       # vues Frontier + segmentation pour solveurs
├─ s41_propagator_solver/         # motifs déterministes (First Pass)
│   └─ pattern_engine.py
├─ s42_csp_solver/             # composantes + backtracking exact
│   ├─ csp_solver.py
│   └─ frontier_reducer.py
├─ controller.py / facade.py   # orchestration & API publique
└─ test_unitaire/              # pipelines debug + overlays
```

### 2.1 Étape 0 – Grid Analyzer (s40)
- `grid_classifier` applique la logique JUST_REVEALED → ACTIVE/FRONTIER/SOLVED en mémoire, sans relecture complète de storage.
- `grid_extractor` construit `SolverFrontierView`, Segmentation et toutes les structures consommées par les solveurs.
- Aucun solver_status n’est calculé ailleurs : c’est le point d’entrée unique pour préparer la frontière, les TO_PROCESS et les vues utilisées par s41/s42.

### 2.2 Frontière Reducer (Phase 1 – règles locales) - ✅ IMPLEMENTÉ
- **s411_frontiere_reducer.py** : propagation déterministe basée sur les valeurs effectives (niveau monocellulaire).
- **Règles locales implémentées** :
  - `effective_value == 0` ⇒ toutes les voisines fermées sont sûres.
  - `effective_value == nb_fermées` ⇒ toutes les voisines fermées sont des mines.
- **Propagation itérative** : boucle jusqu'à stabilisation avec TO_PROCESS adaptatif + simulation d'états.
- **Sorties** : actions sûres immédiates, mise à jour des zones (ACTIVE → SOLVED) et overlays `s41_propagator_solver_overlay/`.

### 2.3 Subset Constraint Propagator (Phase 2 – raisonnement relationnel) - ✅ IMPLEMENTÉ
- **s412_subset_constraint_propagator.py** : applique les règles d'inclusion stricte entre contraintes pour dépasser la monocellule sans lancer de CSP.
- **Représentation canonique** : `Constraint(vars=frozenset(voisins fermés), count=effective_value)`.
- **Boucle** :
  1. Génération des contraintes à partir de la frontière déjà réduite.
  2. Indexation par cellule/|vars| pour ne comparer que les contraintes chevauchantes.
  3. Règle `C1 ⊆ C2` ⇒ `Cdiff = C2 - C1`, avec application immédiate des unités (SAFE/MINE).
  4. Nettoyage des actifs résolus et réexécution jusqu'à stabilité.
- **Objectif** : absorber automatiquement les motifs 121/212/coins sans duplication de logique avec la phase 1.

### 2.4 Propagator Pipeline (Phases 1→3 + refresh) - ✅ IMPLEMENTÉ
- **s410_propagator_pipeline.py** : agrège `s411_frontiere_reducer`, `s412_subset_constraint_propagator`, `s413_advanced_constraint_engine` puis relance Iterative pour absorber les triviales libérées en phase 3.
- **Flux** :
  1. Phase 1 – règles locales (IterativePropagator).
  2. Phase 2 – subset inclusion (SubsetConstraintPropagator).
  3. Phase 3 – pairwise/advanced (AdvancedConstraintEngine).
  4. Phase 3.5 – Iterative refresh (rejoue les règles locales avec toutes les SAFE/FLAG accumulées).
- **Sorties** : `safe_cells`, `flag_cells`, `progress_cells()` et `iterative_refresh` pour informer la couche CSP (nécessaire pour la stabilité composante).

### 2.5 Advanced Constraint Propagator (Phase 3 – unions partielles & pairwise elimination) - ✅ IMPLEMENTÉ
- **s413_advanced_constraint_engine.py** : exploite les intersections partielles entre contraintes pour pousser la propagation avant CSP.
- **Fonctionnalités clés** :
  - Pairwise elimination : calcul des bornes `common_min/common_max` sur `C1 ∩ C2`, forçage des parties communes/exclusives lorsque les bornes coïncident.
  - Inclusion partielle bornée : compare `C_small` avec `C_large ∪ C_extra` (|vars| ≤ 6) via un index inversé pour ne traiter que les contraintes chevauchantes.
  - Génération d’actions SAFE/FLAG supplémentaires, réinjection des contraintes réduites dans la boucle.
- **Intégration** : appelée après la phase subset, partage `simulated_states` et `Constraint` dataclass pour éviter les copies.
- **Logs** : traçabilité explicite (`Pairwise common`, `Pairwise only1`, etc.) pour comprendre les déductions avant CSP.

### 2.5 First Pass Optimization (Pattern Matching + TO_PROCESS) - ✅ IMPLEMENTÉ
**Objectif atteint** : Résolution déterministe rapide avant CSP coûteux.

- **Pipeline TO_PROCESS optimisé** :
  1. **Classification s40** : `FrontierClassifier` → ACTIVE/FRONTIER/SOLVED
  2. **Pré-calcul local** : `neighbors_cache` + `simulated_states` pour efficacité
  3. **Règles effectives** : Valeurs normalisées (nombre - mines confirmées)
  4. **Propagation itérative** : Mise à jour automatique de TO_PROCESS entre itérations
  5. **Early exit** : Arrêt dès stabilisation (pas de changements)
- **Optimisations mémoire** :
  - TO_PROCESS = set (O(1) lookup)
  - Voisins pré-calculés dans `neighbors_cache`
  - États simulés dans `simulated_states` dict
- **Intégration overlays** : Export PNG pour visualisation des décisions

### 2.5 CSP Manager (segmentation + stabilité + CSP) – Second Pass (s43)
- **csp_manager.py** :
  1. **Segmentation** (via `SolverFrontierView`).
  2. **StabilityEvaluator** (`s423_stability_evaluator.py`) pour compter les cycles `no_progress`.
  3. **CSPSolver** sur les composantes stables (≤ `LIMIT_ENUM`).
  4. **Probabilités par zone** (mise à jour `zone_probabilities`, `safe_cells`, `flag_cells`).
- **Intégration** : HybridSolver appelle d’abord `PropagatorPipeline`, puis `CspManager` seulement si aucune action locale n’est trouvée.

### 2.6 Constraint Engine (méthode générique @stratégiers L374-L693)
- **Valeurs effectives** : `effective_value = shown_value - confirmed_mines` (motifs normalisés, cf. L236-L363)
- **Inference loop** :
  1. Construire `constraints = (vars_set, b_effective)` pour chaque case ouverte
  2. Boucler `unit_rule` + `subset_inference` + `pairwise_elimination` jusqu'à stabilité
  3. Si |vars| ≤ LIMIT_ENUM (=20 fixé) → énumération exacte backtracking + pruning
  4. Sinon → marquer composante pour phase probabiliste ou découpage supplémentaire
- **Enum exacte** :
  - Backtracking avec heuristique (ordre par degré, bitmasks, pruning `b_remaining`)
  - Accumuler `forced_all_ones/zeros` pour identifier mines/sûrs
- **Optimisations** :
  - Bitmasks pour subset check O(1)
  - Découper graphe en composantes connexes avant boucle
  - Timeout / fallback si >LIMIT_ENUM ou temps excessif
- **Output** :
  - Actions (safe/flag) + metadata zone probability
  - Cache temporaire (neighbors, flags_count) invalidé dès fin d'itération

### 2.7 Critères de déclenchement CSP (stabilité & composantes)
- **Boucle locale** : les phases 1→3 tournent à chaque itération. Tant qu’une phase produit de nouvelles actions (safe/flag) ou modifie des `effective_value`, on continue la propagation sans CSP.
- **Fixpoint global** : `any_change == False` après Phase 3 ⇒ le graphe de contraintes est stable → éligible CSP.
- **Stabilité par composante** :
  - Chaque composante `C` maintient `no_progress_cycles`.
  - Si `C` n’a subi aucun changement pendant une itération, `no_progress_cycles += 1`, sinon reset à 0.
  - `C` est éligible CSP si `no_progress_cycles >= 1` (ou 2 pour marge) **et** si `C.is_locally_closed` (toutes ses contraintes portent sur ses propres inconnues).
  - CSP appliqué uniquement sur les composantes stables de taille ≤ `LIMIT_ENUM` (18–20 cases).
- **Boucle recommandée** :
  ```text
  loop:
      propagate_phase1()
      propagate_phase2()
      propagate_phase3()
      if any_change: continue

      for comp in frontier_components:
          if comp.is_stable() and comp.size <= LIMIT_ENUM:
              run_CSP(comp)
  ```
- **Objectif** : réserver le CSP aux “résidus logiques” pour éviter les coûts inutiles et garantir que le solveur exact travaille sur des snapshots cohérents.

### 2.8 Debug
- `overlay_renderer.py` : génération PNG pour visualiser les décisions solver (cases colorées).
- `json_exporter.py` : dump des composantes + décisions, utile pour tests.

## 3. API (facade)
```python
@dataclass
class SolverAction:
    cell: tuple[int, int]      # coordonnées
    type: str                  # 'click' | 'flag' | 'unflag'
    confidence: float          # 0.0..1.0
    reasoning: str             # 'pattern' | 'sat' | 'backtrack'

class SolverApi(Protocol):
    def solve(self, unresolved_coords: set[tuple[int, int]], frontier_coords: set[tuple[int, int]], cells: dict[tuple[int, int], GridCell]) -> list[SolverAction]: ...
    def get_stats(self) -> SolverStats: ...
```

## 4. Flux de données
1. **Storage (s3)** → `solve(unresolved, frontier, cells)` : fournit `unresolved_set`, `frontier_set` et les cellules complètes.
2. **Solver** :
   - Filtre `unresolved_set` (exclure résolues d'elles-mêmes) et marque les cellules pertinentes en **TO_PROCESS**.
   - Applique motifs déterministes (PatternEngine) sur les TO_PROCESS.
   - **Calcule `frontier_add/remove`** depuis les TO_PROCESS (propagation analytique).
   - Extrait les **composantes connexes** depuis `frontier_set`.
   - Résout localement les composantes ≤15 variables (LocalSolver SAT/backtracking).
   - Met à jour `unresolved_set` (UNRESOLVED→RESOLVED) et `frontier_set` (via `frontier_add/remove`).
3. **Solver → Pathfinder (s5)** : retourne **uniquement les actions** pour planification viewport.
4. **Pathfinder** utilise les actions pour calculer attractivité et positions fenêtre optimales.
5. **Storage (s3)** sera mis à jour après exécution par s6 et confirmation par s2 (pas de double mise à jour).

- **Séquence stricte** : Storage upsert atomiques, solver lit snapshot complet, traite en interne (batching local) puis écrit une seule fois.
- **TO_PROCESS source** : Vision transmet directement le batch TO_PROCESS détecté dans son dernier upsert (Option B). Solver peut toujours relire `unresolved_set` en secours mais le flux nominal reste Vision→Solver→Storage.
- **Batches extrêmes** : si Vision détecte une avalanche massive (>50k cases), elle peut découper en 2–3 sous-batches pour éviter un bloc monolithique.
- **Verrouillage** : pas de blocage Vision pendant solve → Vision continue à scanner pendant que solver travaille en mémoire.
- **Caches** : voisins pré-calculés recomputés (O(8)) et stockés uniquement dans un cache temporaire par itération (pas de persistance).
- **Data persistantes** : seules les probabilités/zonings du second pass peuvent être stockées dans metadata ; si une cellule de la zone change, recalcul complet obligatoire avant réutilisation.

## 5. Plan d’implémentation
1. **Phase 1 – Infrastructure**
   - Définir `facade.py` (SolverAction, SolverStats, enums).
   - Implémenter `controller.py` minimal : délégation vers PatternEngine + LocalSolver.
2. **Phase 2 – Moteur de motifs**
   - Implémenter `pattern_engine.py` : motifs de base (tous les voisins flags, etc.)
   - Tests unitaires sur grilles 3×3, 5×5.
3. **Phase 3 – Résolution locale**
   - Implémenter `local_solver.py` : SAT pour composantes ≤8, backtrack ≤15.
   - Gestion des transitions UNRESOLVED→TO_PROCESS→RESOLVED et **calcul de `frontier_add/remove`** depuis les TO_PROCESS.
   - Extraction des composantes depuis `frontier_set` (pas de pré-groupage).
4. **Phase 4 – Intégration complète**
   - Solver retourne actions à s5_actionplanner.
   - Tests end-to-end avec grilles réelles.
5. **Phase 5 – Export JSON & optimisations**
   - `export_state()` pour WebExtension (format JSON standard).
   - Optimisations NumPy internes si nécessaire.

## 6. Validation & KPIs
- Taux de résolution sur grilles 9×9 : ≥95% des cellules sûres trouvées.
- Temps par frontière : <5 ms (PatternEngine) + <50 ms (LocalSolver sur ≤15 variables).
- Couverture motifs : ≥80% des actions sûres via motifs (reste au SAT).
- Tests unitaires : toutes les fonctions de `pattern_engine.py` et `local_solver.py`.
- Tests réels : grilles de `temp/games/` et frontières générées depuis `tests/set_screeshot/`.
- Export JSON valide et conforme WebExtension.
- Validation des transitions UNRESOLVED→TO_PROCESS→RESOLVED et de la propagation analytique.
- Profils limites CSP (observé) :
  - `<50` cases contiguës : CSP quasi instantané
  - `50–200` : toujours faisable
  - `200–500` : risque composante lourde, prévoir fallback / découpe
  - `>500` : abandonner CSP → probabilités ou heuristiques globales


## 7. Références
- `development/PLAN_SIMPLIFICATION radicale.md` – sections s4.
- `development/SYNTHESE_pipeline_refonte.md` – §3 Résolution.
- `doc/SPECS/ARCHITECTURE.md` – description couche s4.
- `doc/PIPELINE.md` – flux global.

---
*Ce plan sera mis à jour à mesure que la couche s3_storage expose son API complète (revealed/unresolved/frontier sets).*
