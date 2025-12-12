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
├─ pattern_engine.py      # motifs déterministes
├─ local_solver.py        # composantes + backtracking
├─ frontier_analyzer.py   # extraction composantes, métriques
├─ facade.py              # dataclasses & Protocols
└─ debug/
    ├─ overlay_renderer.py
    └─ json_exporter.py
```

### 2.1 PatternEngine
- Dictionnaire de motifs **3×3 / 5×5** (rotations/reflets compris).
- Encodage en clé (base 16 / bitmask) pour lookup O(1).
- Règles incontournables :
  - `chiffre == nb_drapeaux` ⇒ ouvrir toutes les autres cases adjacentes.
  - `chiffre == nb_drapeaux + nb_cases_fermées` ⇒ poser des drapeaux.
  - Combinaisons classiques : 1-2-1, 2-1-1, 2-2-1, `edge` patterns, etc.
- S'exécute en boucle tant que des actions sont trouvées sur les cellules **TO_PROCESS** de `unresolved_set`.

### 2.2 First Pass Optimization (Pattern Matching + TO_PROCESS)
**Objectif** : Résoudre 80-90% des cas avec règles déterministes rapides avant CSP coûteux.

- **Pipeline TO_PROCESS optimisé** :
  1. **Batching adaptatif** : Découper les révélations massives en batches 20×20/50×50
  2. **Pré-calcul local** : `neighbors + flags_count` stockés temporairement pour chaque TO_PROCESS
  3. **Règles simples** : `mines_non_assignées == 0 → sûrs`, `== nb_voisins → mines`
  4. **Pattern matching** : Lookup tables bitmask 3×3 pour motifs 212, 121, 221, etc.
  5. **Early exit propagation** : RESOLVED immédiat + ajout voisins à TO_PROCESS
- **Optimisations mémoire** :
  - TO_PROCESS = set (O(1) lookup)
  - Precomputed neighbors dans CellData.metadata ou cache temporaire
  - Motifs codés en bitmasks pour matching quasi-instantané
- **Intégration storage** : Lecture via `get_unresolved()`, écriture via `unresolved_remove` + `frontier_add/remove`

### 2.3 LocalSolver (CSP + Probabilités) - Second Pass
**Déclenchement** : Uniquement sur les cas ambigus après first pass.

- Pipeline éprouvé (backup) :
  1. **Segmentation** : Grouper les cellules `frontier_set` par signature de contraintes identiques
  2. **Composantes** : Union-Find sur les zones partageant des contraintes
  3. **CSP Solver** : Résoudre chaque composante indépendamment
  4. **Probabilités** : Moyenne pondérée des solutions par composante
- **Algorithmes éprouvés** :
  - **Zone creation** : `signature = tuple(sorted(constraints))` → groupement O(n)
  - **Union-Find** : Connexité des zones via contraintes partagées
  - **Probabilité par zone** : `P(cell) = E[mines] / |zone|` avec pondération des solutions
- **Actions sûres** : Zones avec P < 0.000001 (0%) ou P > 0.999999 (100%)
- **Best guess** : Zone avec probabilité minimale > 0 (si aucune action sûre)
- Intégration storage passif : Lecture via `get_frontier()` + `get_cells()`, écriture via `frontier_add/remove`

### 2.4 Constraint Engine (méthode générique @stratégiers L374-L693)
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

### 2.3 Debug
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
