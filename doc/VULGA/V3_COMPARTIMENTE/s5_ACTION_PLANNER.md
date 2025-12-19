

## Implémentation actuelle

L’implémentation en place est assumée :

- Façade : `ActionPlannerController.plan(actions)`
- Moteur minimal : `MinimalPathfinder.plan_actions(actions)`

Le moteur groupe les actions par type (FLAG / CLICK / GUESS), conserve l’ordre d’arrivée **à l’intérieur** de chaque groupe, puis concatène.

`PathfinderPlan.overlay_path` existe, mais n’est pas utilisé dans cette version (valeur `None`).

---

## Et la suite

La V2 vise un s5 plus ambitieux (heatmap/frontier, déplacement du viewport), mais cette couche minimaliste est déjà utile : tant que le bot boucle, elle garantit que l’ordre d’exécution reste logique et prévisible.
