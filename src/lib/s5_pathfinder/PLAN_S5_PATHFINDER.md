---
description: Planification viewport et séquencement actions (s5_pathfinder)
---

# PLAN S5 PATHFINDER – Analyse & feuille de route

Document de cadrage qui synthétise les exigences de `PLAN_SIMPLIFICATION radicale.md` et `SYNTHESE_pipeline_refonte.md` pour la couche s5. Il restera la référence tant que l'implémentation n'est pas finalisée.

## 1. Mission
- Recevoir les **actions brutes** du solver (s4) et les **coordonnées frontières actuelles** de s3.
- Calculer les **mises à jour anticipées de la frontière** en fonction des actions planifiées.
- Ordonner les actions et les déplacements viewport pour optimiser la résolution.
- Envoyer à s6 les actions + frontière_anticipée pour validation et exécution.
- Gérer la frontière côté intelligence interne (hors Vision) pour anticiper la capture future.
- Coordonner l'exécution avec s6_action et gérer les retours de confirmation.

## 2. Architecture cible
```
s5_pathfinder/
├─ facade.py              # dataclasses & Protocols
├─ viewport_planner.py    # calcul positions optimales
├─ action_sequencer.py    # ordonnancement mouvements + clics
├─ attractor_engine.py    # métriques attractivité frontière
└─ debug/
    └─ overlay_renderer.py # visualisation viewport + séquence
```

### 2.1 Structures principales
- **ViewportAction**
  - `type`: 'move_viewport' | 'click' | 'flag' | 'unflag'
  - `target`: coordonnées ou delta viewport
  - `priority`: score d'attractivité
  - `expected_state`: état final après action (depuis frontière mise à jour)
- **ViewportPlan**
  - `actions`: liste ordonnée de ViewportAction
  - `viewport_bounds`: rectangle optimal pour résolution
  - `expected_final_frontier`: états après toutes actions
- **AttractorMetrics**
  - `density_actions`: nombre d'actions par zone
  - `distance_factor`: distance depuis viewport actuel
  - `solve_potential`: score de résolvabilité estimée

## 3. API (facade)
```python
@dataclass
class PathfinderRequest:
    actions: list[SolverAction]
    frontier: FrontierSlice
    current_viewport: tuple[int, int, int, int]  # x, y, w, h

@dataclass
class PathfinderPlan:
    sequence: list[ViewportAction]
    viewport_bounds: tuple[int, int, int, int]
    expected_final_frontier: dict[tuple[int, int], GridCell]
    total_actions: int
    estimated_time_ms: int

class PathfinderApi(Protocol):
    def plan_actions(self, actions: list[SolverAction], frontier: FrontierSlice) -> ViewportPlan: ...
    def get_metrics(self) -> PathfinderMetrics: ...
```

## 4. Flux de données
1. **Solver (s4)** → `plan_actions(actions, frontier)` : fournit actions sûres + états attendus.
2. **Pathfinder** :
   - Met à jour les **indicateurs d'attractivité** sur la frontière reçue (incrémental).
   - Calcule la **position viewport optimale** qui maximise les actions dans le champ de vision.
   - **Séquence** les actions : mouvements viewport d'abord, puis clics/drapeaux groupés par zone.
3. **Pathfinder → Action (s6)** : envoie `ViewportPlan(sequence, viewport_bounds)` pour exécution.
4. **Action (s6)** → exécute la séquence, retourne confirmations/résultats.
5. **Pathfinder** met à jour son état interne et peut demander nouvelle planification si nécessaire.

## 5. Plan d'implémentation
1. **Phase 1 – Infrastructure**
   - Définir `facade.py` (ViewportAction, PathfinderPlan, attractors).
   - Implémenter `controller.py` minimal : réception actions + frontière, planification basique.
2. **Phase 2 – Calcul attractivité**
   - Implémenter `attractor_engine.py` : densité actions, distance, potentiel résolution.
   - Mise à jour incrémentale des métriques sur frontière modifiée.
3. **Phase 3 – Planification viewport**
   - Implémenter `viewport_planner.py` : fenêtre glissante optimale, algorithmes de packing.
   - Optimisation multi-viewport si bénéfique.
4. **Phase 4 – Séquencement actions**
   - Implémenter `action_sequencer.py` : ordonnancement mouvements + clics, minimisation déplacements.
   - Groupement géographique des actions.
5. **Phase 5 – Coordination s6 + debug**
   - Intégration avec s6_action pour exécution séquentielle.
   - Overlays PNG pour visualiser viewport + séquence planifiée.

## 6. Validation & KPIs
- Taux de couverture viewport : ≥90% des actions solver dans viewport optimal.
- Temps de planification : <10 ms pour ≤100 actions.
- Optimisation déplacements : réduction ≥30% vs exécution linéaire.
- Tests unitaires : toutes les fonctions de planification et séquencement.
- Tests réels : grilles de `temp/games/` avec actions solver générées.
- Overlays visuels cohérents avec plan calculé.

## 7. Références
- `development/PLAN_SIMPLIFICATION radicale.md` – sections s5.
- `development/SYNTHESE_pipeline_refonte.md` – §5 Pathfinder & viewport.
- `doc/SPECS/ARCHITECTURE.md` – description couche s5.
- `doc/PIPELINE.md` – flux global.

---

*Ce plan sera mis à jour à mesure que les couches s3_storage et s4_solver exposent leurs API complètes.*