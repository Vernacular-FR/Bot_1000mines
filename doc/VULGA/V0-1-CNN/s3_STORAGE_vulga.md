# Journal storage — V0-1 (mettre de l’ordre dans l’état)

Ce journal couvre la période du **28 novembre 2025** au **9 décembre 2025**.
Dans cette première version, le storage n’est pas encore une couche “propre” : il existe parce que sans mémoire, le bot est condamné à refaire la même analyse en boucle.

---

## 28 novembre 2025 — Se souvenir, sinon tout recommence

Au début, je suis tenté de garder l’état “dans ma tête” : je capture, j’analyse, j’agis, et je recommence.
Sauf que la capture est lente, et que la grille est immense : si je re-scan des zones déjà connues, je paye le coût deux fois.

Très vite, je comprends que le bot a besoin d’une mémoire minimale :

- pour ne pas re-traiter les cases déjà révélées,
- pour garder un historique cohérent des informations,
- et pour alimenter le solver avec un état stable.

---

## 5 décembre 2025 — Les invariants deviennent une obsession

Dès que plusieurs modules “touchent” l’état (vision, solver, exécution d’actions), les incohérences apparaissent.
Et je me rends compte que je ne peux pas raisonner tant que je n’ai pas des invariants simples, presque scolaires.

Je finis par converger vers une représentation qui sera la base de la suite :

`revealed` pour “ce qui est connu”, `unresolved` pour “ce qui doit être traité”, et `frontier` pour “les inconnues pertinentes autour du connu”.

Dans V0-1, ce n’est pas encore maîtrisé : je suis surtout en train de découvrir *quelles informations* je dois stocker, et *comment* éviter que tout parte en vrille quand je fais une mise à jour.

---

## 9 décembre 2025 — La conclusion avant V2

Je termine cette phase avec une conviction : le storage doit être **passif**, et son rôle doit être de préserver la cohérence, pas de “réfléchir”.

La refonte V2 (dès le **10 décembre**) va transformer ce pressentiment en règles claires : grille sparse, mises à jour atomiques, et gestion explicite des sets `revealed/unresolved/frontier`.