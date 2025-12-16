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

Le point critique, c’est la réduction : les cases résolues par le reducer doivent aussi apparaître dans le combiné, sinon on a l’impression que le CSP "invente" des actions.
En rendant ces actions visibles au même niveau que le reste (opaque), le debug redevient lisible.

---

## 16 décembre 2025 — Fusion des actions reducer + CSP dans GameLoopService

Le pipeline CSP fonctionne bien, mais les actions du reducer n’étaient pas exécutées en jeu. Le problème venait de `GameLoopService` qui ne récupérait que `solver_actions` et ignorait `reducer_actions`.

Correction apportée :
- Ajout de `solve_snapshot_with_reducer_actions` dans `StorageSolverService` pour construire les `SolverAction` depuis `reducer_safe/reducer_flags`
- Modification de `GameLoopService.execute_single_pass` pour fusionner reducer_actions + solver_actions
- Priorisation des actions déterministes (CLICK/FLAG) avant les GUESS
- Augmentation de `max_component_size` à 500 pour traiter des frontières plus grandes

Résultat : le bot exécute maintenant toutes les actions sûres (reducer + CSP) avant un éventuel guess. Les logs montrent bien les reducer_actions avec le tag `frontiere-reducer`.

---

## 16 décembre 2025 — Pilotage solver par storage (ACTIVE/frontier + zones)

En avançant sur la V2, je clarifie le contrat entre s3 et s4 :

- le solver click-based travaille d’abord sur `active_set` (OPEN_NUMBER avec voisins fermés)
- le CSP est déclenché ensuite sur la frontière réellement pertinente : `frontier_set` + zones marquées `TO_PROCESS`

Le point important est que je ne veux plus “tout re-CSP tout le temps”.
Quand une zone est bloquée (pas de déduction sûre), elle passe en `BLOCKED` et elle est ignorée tant qu’elle ne change pas.

Cette mémoire de zones est portée par une ZoneDB (index dérivé via `zone_id`), ce qui permet à s4 de ne lancer le CSP que quand c’est utile.