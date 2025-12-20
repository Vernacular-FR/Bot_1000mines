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

Il consomme également `TO_VISUALIZE` (écrit par le solver) pour cadrer la re-capture.

Justification : le solver doit rester un moteur de déduction (SAFE/FLAG/GUESS). Toute logique “d’exécution astucieuse” (double-clic, clics opportunistes) est concentrée ici pour éviter de dupliquer de la logique et pour garder s4 déterministe.

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

L’implémentation actuelle (`MinimalPathfinder`) applique un tri stable, et **consomme deux listes** :
- `actions` (SAFE/FLAG/GUESS) issues du solver
- `cleanup_actions` (bonus) issues du module cleanup

Ordre d’exécution :
1. `FLAG`
2. `CLICK` (non-cleanup) → convertis en **double-clic**
3. `CLICK` de cleanup (raisoning contient “cleanup”) → **simple clic**
4. `GUESS` en dernier

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

- **Double-clic SAFE** : traduire les `CLICK` solver en double action côté exécution (déjà implémenté).
- **Séparation cleanup** : exécuter les `cleanup_actions` (bonus) en simple clic, hors métriques solver/CSP.
- **Ménage local (optionnel)** : après avoir cliqué un `SAFE`, ajouter éventuellement quelques clics opportunistes sur des `ACTIVE` adjacentes pour déclencher une résolution plus loin, sans que s4 ne contienne de logique dédiée.
- **Overlay plan** : produire un `overlay_path` (audit des actions planifiées).
- **Options solver** : `allow_guess` et `enable_cleanup` sont pilotés en s4 ; s5 consomme simplement les deux listes d’actions (solver + cleanup) fournies.

Clarification : le planner est agnostique du mode solver (réduction vs CSP). Il ne fait qu’ordonner/exécuter les actions qui lui sont données (flags, safes, cleanup), sans heuristique de priorité “SAFE-first”.

## 7. Optimisations de performance (2025-12-20)

### Logs Simplifiés
- **Avant** : Log individuel de chaque action FLAG/SAFE.
- **Après** : Log agrégé "X flags + Y safes executed".
- **Bénéfices** : Réduction significative du volume de logs, meilleure lisibilité console.

### Gestion des Mouvements Manuels
- **Problème** : Quand l'utilisateur bougeait manuellement, le bot continuait avec des données périmées.
- **Solution** : Le planner retourne `success=False` pour empêcher l'exécution du solver.
- **Bénéfices** : Robustesse accrue face aux interactions utilisateur.

## 8. Référence – Dumb Solver Loop

La stratégie actuelle (réduction de frontière systématique, bypass CSP si assez d'actions, sinon CSP sur `TO_PROCESS`) est décrite ici :

`doc/FOLLOW_PLAN/s44_dumb_solver_loop.md`