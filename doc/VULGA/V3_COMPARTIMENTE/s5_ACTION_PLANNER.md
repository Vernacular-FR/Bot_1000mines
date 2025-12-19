

## Implémentation actuelle

L’implémentation en place est assumée :

- Façade : `ActionPlannerController.plan(actions)`
- Moteur minimal : `MinimalPathfinder.plan_actions(actions)`

Le moteur groupe les actions par type (FLAG / CLICK / GUESS), conserve l’ordre d’arrivée **à l’intérieur** de chaque groupe, puis concatène.

`PathfinderPlan.overlay_path` existe, mais n’est pas utilisé dans cette version (valeur `None`).

---

## Implémentation V3 (Agent Actif)

Le planner n'est plus un simple "secrétaire" qui fait des listes. C'est le **bras armé** du bot :

1.  **Ordonnancement** : Il trie toujours les actions (Drapeaux d'abord, puis Safes).
2.  **Exécution Directe** : Il possède le driver Selenium et clique lui-même sur les cases.
3.  **Surveillance** : Il regarde le score et les vies. S'il y a une explosion, il gère la pause de 2s tout seul.
4.  **Précision Chirurgicale** : Il utilise des coordonnées relatives à l'anchor, ce qui le rend insensible aux mouvements du viewport.

---

## Conclusion V3

La couche s5 est maintenant le centre névralgique de l'interaction. Elle garantit que les décisions du solver sont appliquées avec une fiabilité maximale, peu importe les conditions de navigation.
