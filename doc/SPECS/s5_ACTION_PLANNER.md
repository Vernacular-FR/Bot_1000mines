---
description: Spécification technique de la couche s5_actionplanner (planification minimale d'actions)
---

# S05 ACTIONPLANNER – Spécification technique

## 1. Mission (ce que fait s5)

s5_actionplanner transforme une liste d’actions solver (`SolverAction`) en un plan d’exécution simple (`PathfinderPlan`) consommable par s6_action.

Dans la version actuelle, s5 est volontairement minimal :
- il **ordonne** et **convertit** des actions
- il ne fait **aucun raisonnement** sur l’état du jeu
- il ne fait **aucun déplacement viewport**

## 2. Contrat (entrées / sorties)

### 2.1 Entrée : `SolverAction`

Type défini dans `src/lib/s4_solver/facade.py` :
- `cell: (x, y)`
- `type: SolverActionType` (`FLAG`, `CLICK`, `GUESS`)
- `confidence: float`
- `reasoning: str`

### 2.2 Sortie : `PathfinderPlan`

Type défini dans `src/lib/s5_actionplanner/facade.py` :
- `actions: List[PathfinderAction]`
- `overlay_path: Optional[str] = None`

`PathfinderAction` :
- `type: str` ("click" | "flag" | "guess")
- `cell: (x, y)`
- `confidence: float`
- `reasoning: str`

### 2.3 API

- `ActionPlannerController.plan(actions: List[SolverAction]) -> PathfinderPlan`

## 3. Règles actuelles (implémentation minimale)

### 3.1 Ordre d’exécution

L’implémentation actuelle (`MinimalPathfinder`) applique un tri stable :
- `FLAG` d’abord
- `CLICK` ensuite
- `GUESS` en dernier

Le tri est stable : l’ordre relatif d’entrée est conservé à l’intérieur de chaque catégorie.

### 3.2 Conversion

Chaque `SolverAction` est convertie en `PathfinderAction` en conservant :
- `cell`
- `confidence`
- `reasoning`

## 4. Invariants (ce que s5 ne doit pas faire)

- s5 ne modifie pas la sémantique des actions : il ne fait que réordonner / convertir.
- s5 ne crée jamais de coordonnées nouvelles.
- s5 ne lit pas la grille : la vérité jeu (topologie, focus, etc.) vit dans s3_storage (cf `doc/SPECS/s3_STORAGE.md`).

## 5. Intégration avec s6_action

s6 exécute les actions navigateur à partir de `PathfinderPlan.actions`.

Convention minimale :
- `type == "flag"` déclenche un clic droit
- sinon un clic gauche (click/guess)

## 6. Évolutions prévues (décisions récentes)

Ces points sont des décisions de design, mais ne sont pas tous implémentés dans `MinimalPathfinder` :

- **Double-clic SAFE** : traduire certains `CLICK` en double action côté exécution, pour exploiter l’auto-résolution native du jeu.
- **TO_VISUALIZE** : après exécution, marquer des cellules comme à re-capturer (ce statut vit dans `TopologicalState`, cf `doc/SPECS/s3_STORAGE.md`).
- **Overlay plan** : produire un `overlay_path` (audit des actions planifiées).

## 7. Référence – Dumb Solver Loop

La stratégie click-based (multi-cycles sur `active_set`, déclenchement CSP sur les zones `TO_PROCESS`) est décrite ici :

`src/services/s44_dumb_solver_loop.md`