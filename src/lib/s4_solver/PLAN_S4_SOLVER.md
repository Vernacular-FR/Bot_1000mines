---
description: Feuille de route s4_solver (PatternEngine + LocalSolver)
---

# PLAN S4 SOLVER – Synthèse & objectifs

Document de travail qui synthétise les exigences du **PLAN DE SIMPLIFICATION RADICALE** et de **SYNTHESE_pipeline_refonte.md** pour la couche s4. Il servira de référence tant que l’implémentation n’est pas finalisée.

## 1. Mission
- Transformer la frontière compacte de s3 en **actions sûres** (clics, drapeaux) sans jamais modifier la frontière elle-même.
- Calculer lui-même les composantes connexes depuis la FrontierSlice (pas de pré-groupage).
- Retourner **uniquement les actions** à s5_pathfinder, PAS de mise à jour de frontière.
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
- S’exécute en boucle tant que des actions sont trouvées.

### 2.2 LocalSolver
- Pipeline :
  1. `frontier_analyzer` extrait les composantes connexes sur la frontière (cases fermées + contraintes autour).
  2. Si composante ≤ 15 variables → backtracking exact (SAT-like). Appliquer toutes les décisions communes.
  3. Sinon → heuristique (probabilités locales contrôlées) ou fallback (CNN ponctuel) **optionnel mais non prioritaire**.
- Doit produire pour chaque composante :
  - Actions sûres (open/flag).
  - Liste résiduelle (ambiguïté) pour pathfinder/heuristique.

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
    def solve(self, frontier: FrontierSlice) -> list[SolverAction]: ...
    def get_stats(self) -> SolverStats: ...
```

## 4. Flux de données
1. **Storage (s3)** → `solve(frontier)` : fournit contraintes + cellules fermées adjacentes.
2. **Solver** :
   - Calcule les **composantes connexes** lui-même à partir de la FrontierSlice.
   - Applique motifs déterministes (PatternEngine) sur chaque composante.
   - Résout localement les composantes ≤15 variables (LocalSolver SAT/backtracking).
3. **Solver → Pathfinder (s5)** : retourne **uniquement les actions** pour planification viewport.
4. **Pathfinder** utilise les actions pour calculer attractivité et positions fenêtre optimales.
5. **Storage (s3)** sera mis à jour après exécution par s6 et confirmation par s2 (pas de double mise à jour).

## 5. Plan d’implémentation
1. **Phase 1 – Infrastructure**
   - Définir `facade.py` (SolverAction, SolverStats, enums).
   - Implémenter `controller.py` minimal : délégation vers PatternEngine + LocalSolver.
2. **Phase 2 – Moteur de motifs**
   - Implémenter `pattern_engine.py` : motifs de base (tous les voisins flags, etc.)
   - Tests unitaires sur grilles 3×3, 5×5.
3. **Phase 3 – Résolution locale**
   - Implémenter `local_solver.py` : SAT pour composantes ≤8, backtrack ≤15.
   - Extraction des composantes depuis FrontierSlice (pas de pré-groupage).
4. **Phase 4 – Intégration complète**
   - Solver retourne actions à s5_pathfinder.
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

## 7. Références
- `development/PLAN_SIMPLIFICATION radicale.md` – sections s4.
- `development/SYNTHESE_pipeline_refonte.md` – §3 Résolution.
- `doc/SPECS/ARCHITECTURE.md` – description couche s4.
- `doc/PIPELINE.md` – flux global.

---
*Ce plan sera mis à jour à mesure que la couche s3_storage expose son API complète.* 
