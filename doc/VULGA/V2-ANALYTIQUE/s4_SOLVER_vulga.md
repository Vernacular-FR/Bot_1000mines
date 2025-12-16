# Journal solver — V2 (CSP optimisé, autonome)

Ce journal couvre la **V2 à partir du 10 décembre 2025**.
L’objectif n’est pas de rajouter un nouveau solver “en plus”. L’objectif est d’obtenir un pipeline qui marche seul, avec une logique claire : réduire d’abord, résoudre ensuite.

---

## 10 décembre 2025 — Formaliser la propagation

Je restructure le raisonnement en phases.
Au lieu d’un grand bloc monolithique, je fais une propagation qui commence par des règles locales, puis monte en complexité (contraintes entre voisines), jusqu’au point où le problème devient suffisamment stable.

L’effet est immédiat : ce n’est pas forcément “plus intelligent”, mais c’est plus contrôlable.
Et surtout, ça prépare un terrain propre pour un solveur exact.

---

## 14 décembre 2025 — Le déclic : la réduction frontière doit précéder le zonage

Le vrai problème historique du CSP, je finis par le voir clairement : les zones tronquées.
Ce n’est pas juste “le CSP qui est mauvais”. C’est moi qui lui donnais des composantes instables, découpées trop tôt.

Et comme si ça ne suffisait pas, je me rends compte qu’en V2 j’avais ajouté par inadvertance un garde-fou de **taille maximale** sur certaines frontières : résultat, même des frontières complètes (mais un peu longues) ne passaient plus au solver.
Le jour où je le rends configurable (au lieu de le subir), je récupère enfin des cas qui auraient dû être traités.

La décision qui change tout est simple :

Je fais la réduction frontière **avant** de segmenter et d’appeler le CSP.

En pratique, ça donne un pipeline CSP optimisé, autonome : le reducer fait le ménage, puis le CSP travaille sur un snapshot cohérent.

Les benchmarks confirment ce basculement : on passe d’un CSP pénible et imprévisible à un solver qui devient compétitif, et souvent meilleur, tout en étant plus rapide que l’ancien hybride.

---

## 15 décembre 2025 — Overlays : voir le raisonnement, pas juste le résultat

Une fois le pipeline live branché, le besoin change : je ne veux pas seulement “des actions”, je veux comprendre pourquoi.
Je verrouille donc la génération des overlays solver par partie, avec une logique simple : un overlay d’état (avant CSP), un overlay de segmentation, et un overlay combiné.

Le point critique, c’est la réduction : les cases résolues par le reducer doivent aussi apparaître dans le combiné, sinon on a l’impression que le CSP “invente” des actions.
En rendant ces actions visibles au même niveau que le reste (opaque), le debug redevient lisible.