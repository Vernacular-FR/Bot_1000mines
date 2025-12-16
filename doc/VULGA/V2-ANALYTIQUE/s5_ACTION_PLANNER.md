
# Journal action planner — V2 (planification minimale)

Ce journal couvre la **V2 à partir du 10 décembre 2025**.
Dans l’architecture s0→s6, le rôle de s5 n’est pas de “résoudre” : il sert à transformer une liste d’actions trouvées par le solver en une **séquence d’exécution** stable et cohérente.

Aujourd’hui, l’Action Planner est volontairement minimal : il ne fait **pas** de navigation viewport, il ne fait **pas** de calcul de trajectoire, et il n’invente **aucune** action. Il met juste de l’ordre.

---

## 16 décembre 2025 — Un planner minimal, mais un contrat indispensable

Quand le solver a commencé à produire beaucoup d’actions, il fallait une règle simple et constante :

1. **Drapeaux d’abord** (FLAG)
2. **Clics sûrs ensuite** (CLICK)
3. **Guesses en dernier** (GUESS)

Ce tri évite des comportements absurdes (ouvrir avant de marquer une mine évidente), et il fournit un contrat clair pour s6 (exécution) : un plan linéaire, déjà ordonné.

Concrètement :

- s4 produit des `SolverAction` (avec type, cell, confidence, reasoning)
- s5 transforme ça en `PathfinderPlan` composé de `PathfinderAction`
- s6 convertit ensuite ces `PathfinderAction` en actions navigateur (clic gauche / clic droit)

Cette séparation est importante : s4 “décide”, s5 “ordonne”, s6 “agit”.

En parallèle, j’ai acté deux évolutions simples et très rentables :
- **Double-clic SAFE** : exécuter certains `CLICK` comme un double-clic pour déclencher l’auto-résolution du jeu quand les conditions sont réunies.
- **TO_VISUALIZE** : marquer les zones/cellules à re-capturer après exécution (besoin de vision, pas une classification du jeu).

Référence stratégie click-based (dumb solver loop) : `src/services/s44_dumb_solver_loop.md`.

---

## Implémentation actuelle

L’implémentation en place est assumée :

- Façade : `ActionPlannerController.plan(actions)`
- Moteur minimal : `MinimalPathfinder.plan_actions(actions)`

Le moteur groupe les actions par type (FLAG / CLICK / GUESS), conserve l’ordre d’arrivée **à l’intérieur** de chaque groupe, puis concatène.

`PathfinderPlan.overlay_path` existe, mais n’est pas utilisé dans cette version (valeur `None`).

---

## Et la suite

La V2 vise un s5 plus ambitieux (heatmap/frontier, déplacement du viewport), mais cette couche minimaliste est déjà utile : tant que le bot boucle, elle garantit que l’ordre d’exécution reste logique et prévisible.

