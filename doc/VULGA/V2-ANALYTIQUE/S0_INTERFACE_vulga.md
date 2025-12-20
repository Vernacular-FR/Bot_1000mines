# Journal interface — V2 (contrat et repère)

Ce journal couvre la **V2 à partir du 10 décembre 2025**.
L’objectif n’est plus juste “arriver à cliquer”. L’objectif, c’est que l’interface devienne une brique fiable, presque ennuyeuse, sur laquelle tout le reste peut se poser.

---

## 10 décembre 2025 — Réduire l’interface à un contrat minimal

Je force une idée très stricte : l’interface doit se résumer à quelques opérations stables.
Tout le reste doit être reconstruit à partir d’un repère commun (anchor + conversion cellule→pixel).

---

## 12 décembre 2025 — Cohérence capture / interface

Je comprends que l’interface ne peut pas vivre séparée de la capture.
Si je déplace la vue d’une façon et que je capture d’une autre, je reconstruis des décalages artificiels.

---

## 14 décembre 2025 — Une base prête pour l’extension

En stabilisant le contrat, je prépare la suite : une interface qui pourra migrer vers une extension navigateur.
L’idée est simple : si je peux décrire “où je suis” et “où je clique” de manière stable, alors je peux changer l’implémentation (Selenium → extension) sans réécrire le bot.

---

## 15 décembre 2025 — Fin de session : une seule porte de sortie

Je corrige un problème très classique : quand plusieurs couches “ferment” la session, on finit par fermer trop tôt, ou au mauvais moment.
En V2, je verrouille le comportement : la session (et donc le navigateur) est fermée une seule fois, par le pilote principal, après la boucle.

Ce détail est important en pratique : je peux laisser le navigateur ouvert le temps d’inspecter une partie, puis valider la fermeture explicitement (prompt Entrée), sans qu’une passe de solver ne vienne interrompre le diagnostic.

---

## 16 décembre 2025 — Actions JS et boucle offscreen

En verrouillant l’exécution des actions via JS, je peux cliquer/flag sans dépendre du viewport.
La conséquence sur le pipeline est directe : quand le solver annonce une cellule `SAFE`, il peut la marquer `TO_VISUALIZE` pour forcer une relecture à l’itération suivante, même si elle est hors champ.