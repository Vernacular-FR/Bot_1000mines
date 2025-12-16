# Journal storage — V2 (cohérence d’abord)

Ce journal couvre la **V2 à partir du 10 décembre 2025**.
Dans cette refonte, je ne veux plus d’un storage “intelligent” qui fait un peu de tout. Je veux un storage passif, simple, et cohérent, qui sert de base solide à la vision et au solver.

---

## 10 décembre 2025 — Repartir sur des invariants explicites

Je formalise enfin ce que j’avais appris en V0-1 : si l’état n’est pas cohérent, aucun solver ne peut être fiable.
Le storage devient donc une brique qui garantit des invariants et qui expose des structures claires.

La grille devient une mémoire unique, et je conserve l’idée des trois ensembles, parce qu’ils répondent à trois besoins différents :

`revealed` pour éviter de re-scanner, `unresolved` pour savoir quoi traiter, et `frontier` pour isoler les inconnues utiles.

---

## 12 décembre 2025 — Centraliser les mises à jour

Je règle un problème très concret : quand plusieurs étapes modifient l’état, on finit par créer des incohérences subtiles.
La solution V2 est simple : toutes les mises à jour passent par une voie centrale, appliquée en batch, avec vérification des invariants.

Ce choix n’est pas “sexy”, mais il change la vie : je passe de bugs fantômes à des erreurs reproductibles.

---

## 14 décembre 2025 — Adapter l’état aux besoins du solver

Au moment où le solver devient plus structuré, le storage doit transporter plus d’informations :
ce que la vision a vu (raw), ce que le bot croit (logical), et où en est le traitement (solver_status).

L’idée clé reste la même : le storage stocke, le solver raisonne.

 ---

## 15 décembre 2025 — Une base commune pour les overlays et le debug

Quand je branche le pipeline live, je réalise que le storage ne doit pas seulement être cohérent “dans l’absolu”.
Il doit aussi être cohérent dans le temps : une partie = un dossier, une série d’artefacts, un état que je peux relire.

C’est là que l’arborescence par `game_id` devient précieuse : elle évite que des overlays ou des captures de runs différents se mélangent.

---

## 16 décembre 2025 — Cohérence terminologique et alignement SPECS
clarifie aussi la mémoire de pertinence :
- ACTIVE : `TO_TEST / TESTED / STERILE`
- FRONTIER : `TO_PROCESS / PROCESSED / BLOCKED`

Et j’introduis une ZoneDB (index dérivé) pour regrouper la frontière en zones CSP via `zone_id`.

Aujourd'hui je finalise le contrat storage/solver en alignant toute la documentation sur un seul modèle :
- **Sets** : `revealed_set / active_set / frontier_set` (plus de `unresolved`)
- **FocusLevel** : nomenclature explicite `TO_TEST / TESTED / STERILE` (ACTIVE) et `TO_PROCESS / PROCESSED / BLOCKED` (FRONTIER)
- **ZoneDB** : index dérivé basé sur `zone_id` pour piloter le CSP uniquement sur les zones `TO_PROCESS`

`revealed` pour éviter de re-scanner, `active` pour savoir quoi exploiter en click-based, et `frontier` pour isoler les inconnues utiles.
Concrètement :
- `active_set` = OPEN_NUMBER avec voisins UNREVEALED
- `frontier_set` = UNREVEALED adjacent à une ACTIVE

Le storage est maintenant une brique parfaitement passive, mais avec une mémoire de pertinence qui permet au solver de ne travailler que sur ce qui compte.
