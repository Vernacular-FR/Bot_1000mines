---
description: Exécution actions brutes et coordination avec viewport (s6_action)
---

# PLAN S6 ACTION – Analyse & feuille de route

Document de cadrage qui synthétise les exigences de `PLAN_SIMPLIFICATION radicale.md` et `SYNTHESE_pipeline_refonte.md` pour la couche s6. Il restera la référence tant que l'implémentation n'est pas finalisée.

## 1. Mission
- Recevoir les **plans d'actions séquencés** de s5_actionplanner (déplacements viewport + clics/drapeaux + frontière_anticipée).
- **Exécuter les actions brutes** sur l'interface utilisateur via Selenium ou extension navigateur.
- **Valider les mises à jour de frontière** envoyées par actionplanner et les appliquer si l'exécution réussit.
- Gérer les **timings**, **erreurs** et **confirmations** d'exécution pour les couches supérieures.
- Maintenir une **interface unique** remplaçable (Selenium aujourd'hui, WebExtension demain).

## 2. Architecture cible
```
s6_action/
├─ facade.py              # dataclasses & Protocols
├─ click_executor.py      # exécution actions brutes
├─ timing_manager.py      # gestion délais et cadences
├─ error_handler.py       # détection et récupération erreurs
└─ debug/
    └─ action_logger.py   # traçabilité exécution
```

### 2.1 Structures principales
- **RawAction**
  - `type`: 'click' | 'flag' | 'unflag' | 'move_viewport'
  - `target`: coordonnées (x, y) ou delta viewport
  - `timing_ms`: délai avant/après action
  - `expected_result`: état final attendu (optionnel)
- **ActionBatch**
  - `actions`: liste ordonnée de RawAction
  - `viewport_bounds`: rectangle cible pour l'exécution
  - `frontier_updates`: coordonnées à ajouter/retirer de la frontière (validation)
  - `timeout_ms`: timeout global pour le batch
- **ExecutionResult**
  - `success`: booléen global
  - `executed_actions`: liste des actions avec statut individuel
  - `frontier_validated`: booléen indiquant si les mises à jour frontière ont été appliquées
  - `errors`: liste des erreurs rencontrées

## 3. API (facade)
```python
@dataclass
class ActionRequest:
    batch: ActionBatch
    current_viewport: tuple[int, int, int, int]  # x, y, w, h

@dataclass
class ActionResult:
    success: bool
    executed_count: int
    failed_count: int
    frontier_validated: bool
    errors: list[str]
    final_viewport: tuple[int, int, int, int]

class ActionControllerApi(Protocol):
    def execute_batch(self, request: ActionRequest) -> ActionResult: ...
    def get_current_viewport(self) -> tuple[int, int, int, int]: ...
    def abort_execution(self) -> None: ...
```

**Important** : `execute_batch()` valide et applique les mises à jour de frontière si l'exécution réussit.

## 4. Flux de données
1. **Pathfinder (s5)** → `execute_batch(ActionBatch)` : fournit séquence d'actions optimisée.
2. **Action** :
   - Valide la cohérence du batch (actions dans viewport, timing réaliste).
   - Exécute séquentiellement : déplacements viewport d'abord, puis clics/drapeaux groupés.
   - Gère les timings entre actions pour éviter la surcharge UI.
3. **Action → Vision/Storage** : signale la fin d'exécution pour déclencher nouvelle capture.
4. **Action → Pathfinder** : retourne résultats et erreurs pour ajustement futurs plans.

## 5. Plan d'implémentation
1. **Phase 1 – Infrastructure**
   - Définir `facade.py` (RawAction, ActionBatch, ActionResult).
   - Implémenter `controller.py` minimal : réception batch, exécution séquentielle basique.
2. **Phase 2 – Exécution Selenium**
   - Implémenter `click_executor.py` : ActionChains + execute_script pour clics précis.
   - Gestion des déplacements viewport (scrolls, zooms).
   - Tests unitaires sur pages de test.
3. **Phase 3 – Timing et erreurs**
   - Implémenter `timing_manager.py` : cadences optimales, délais adaptatifs.
   - Implémenter `error_handler.py` : détection blocages, retries automatiques.
4. **Phase 4 – Coordination complète**
   - Intégration avec s5_actionplanner pour exécution séquentielle.
   - Retours d'exécution vers s5 pour ajustement plans.
5. **Phase 5 – Extension-ready + debug**
   - Préparer interface pour remplacement Selenium → WebExtension.
   - Logging détaillé des exécutions pour debugging.

## 6. Validation & KPIs
- Taux de réussite exécution : ≥98% des actions exécutées sans erreur.
- Temps par batch : <200 ms pour ≤50 actions (incluant déplacements).
- Gestion erreurs : récupération automatique ≥90% des cas.
- Tests unitaires : toutes les fonctions d'exécution et gestion timing.
- Tests réels : exécution sur grilles de `temp/games/` avec actions générées par s5.
- Logs traçables pour debugging post-mortem.

## 7. Références
- `development/PLAN_SIMPLIFICATION radicale.md` – sections s6.
- `development/SYNTHESE_pipeline_refonte.md` – §5 Pathfinder & Action.
- `doc/SPECS/ARCHITECTURE.md` – description couche s6.
- `doc/PIPELINE.md` – flux global.

---

*Ce plan sera mis à jour à mesure que la couche s5_actionplanner expose son API complète.*