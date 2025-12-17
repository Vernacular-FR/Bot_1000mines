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

Le point important est que je ne veux plus “tout re-CSP tout le temps".
Quand une zone ne produit plus de déduction sûre, elle passe en `PROCESSED` et elle est ignorée tant qu’elle ne change pas.

Et quand s4 annonce une cellule `SAFE`, il la passe en `TO_VISUALIZE` pour forcer une relecture à l’itération suivante.

La logique derrière ce choix :

- s4 doit rester un moteur de déduction : il produit des `SAFE/FLAG/GUESS`.
- Le progrès en jeu doit venir d’abord des `SAFE` (inconnues cliquables) : c’est plus efficace que d’essayer de déclencher le moteur en recliquant des `ACTIVE`.
- La réduction de frontière est un mode “rapide” suffisant tant qu’elle sort des actions ; le CSP n’est appelé qu’en mode “lourd” quand la réduction stagne.
- Tout comportement d’exécution (double-clic, ménage local) est hors solver et appartient à s5.

Cette mémoire de zones est portée par une ZoneDB (index dérivé via `zone_id`), ce qui permet à s4 de ne lancer le CSP que quand c’est utile.

---

## 17 décembre 2025 — Bug “reclustering fantôme” : pourquoi la repromotion ne marchait pas

J’ai eu un cas typique de bug d’architecture : tout semblait “déjà là”, mais une étape cruciale n’était jamais appliquée en vrai.

La vision injectait des cellules en `JUST_VISUALIZED`, et le state analyzer savait déterminer quelles cellules devenaient `ACTIVE`, `SOLVED` ou `FRONTIER`. Sauf qu’en pratique, ce reclassement restait implicite : le solver ne récupérait pas forcément un snapshot où ces nouveaux statuts existaient réellement.

Conséquence : le mécanisme qui rend le solver efficace sur la durée (la **re-promotion** des focus levels) ne pouvait pas se déclencher correctement. Une nouvelle info issue de la vision ne “réveillait” pas les voisines qui étaient déjà `REDUCED` ou les zones `PROCESSED`.

Fix :
- j’écris désormais le reclustering **dans storage** juste après l’upsert vision (donc avant extraction du batch solver)
- je conserve un second point de repromotion après les décisions du solver (SAFE/FLAG), parce que ces décisions changent aussi la topologie (`TO_VISUALIZE` / `SOLVED`) et doivent relancer le voisinage.