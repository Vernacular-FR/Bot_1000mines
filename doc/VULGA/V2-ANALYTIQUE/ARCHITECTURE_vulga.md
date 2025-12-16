# Journal architectural — V2 (refonte analytique)

Ce journal couvre la **V2 à partir du 10 décembre 2025**.
L’idée n’est pas d’empiler des améliorations : c’est de repartir sur un pipeline lisible, où chaque couche fait une chose, et où la perf est une contrainte assumée.

---

## 10 décembre 2025 — Le point de départ : clarifier le pipeline

Je prends une décision simple : l’architecture doit être compréhensible en une phrase.
Donc je découpe le bot en couches (s0 → s6) et je force les contrats.

Ce découpage a un effet immédiat : je peux enfin améliorer une brique sans casser les autres.
Et surtout, je peux commencer à bencher et à instrumenter, parce que je sais exactement “qui fait quoi”.

---

## 12 décembre 2025 — Capture + vision : un couple indissociable

En pratique :

- Tester régulièrement la reconnaissance (`tests/test_s2_vision_performance.py`) pour valider la calibration des seuils et l’ordre de priorité.
- Remplacer Selenium par CDP/extension dès que possible pour fiabiliser la capture et le clic.
- Penser à documenter chaque ajustement de seuil (vision) ou de configuration solver dans les journaux techniques.

### Règle structurante : responsabilités + export_root unique

Je fixe ici une règle qui doit rester vraie tout au long de V2.
Avec l’architecture clarifiée, je peux enfin comparer proprement les pipelines et converger vers une solution qui marche seule : un solver CSP optimisé, autonome, dont la force vient d’un pré-traitement systématique (réduction frontière) plutôt que d’une hybridation floue.

- **Toute la logique au plus bas niveau** : la logique vit dans les modules `src/lib/*` (calculs, conventions de nommage, choix des sous-dossiers, formats de sortie).
- **Controllers = passe-plats** : ils exposent une API propre, mais n’embarquent pas de logique métier.
- **Services = orchestration uniquement** : ils déclenchent les étapes dans le bon ordre (capture → vision → solver → action), sans reconstruire des chemins ou “inventer” des noms.

Conséquence directe :

- `export_root` (racine de partie) est **la seule information de chemin** transmise depuis l’orchestration.
- Les overlays sont des “dead ends” : ils se sauvegardent eux-mêmes et ne doivent pas imposer de chemins en amont.

Arbo officielle sous `{base} = export_root` :

- `s1_raw_canvases/`
- `s1_canvas/`
- `s2_vision_overlay/`
- `s40_states_overlays/`
- `s42_segmentation_overlay/`
- `s42_solver_overlay/`
- `s43_csp_combined_overlay/`

La capture s1 produit les fichiers consommés par vision, et la vision/solver produisent leurs overlays dans leurs sous-dossiers dédiés.
La V2 verrouille donc un principe : l’information doit venir du canvas de manière la plus directe possible, et la vision doit rester déterministe.

---

## 14 décembre 2025 — Le solver devient autonome

La dernière pièce, c’est la résolution.
Avec l’architecture clarifiée, je peux enfin comparer proprement les pipelines et converger vers une solution qui marche seule : un solver CSP optimisé, autonome, dont la force vient d’un pré-traitement systématique (réduction frontière) plutôt que d’une hybridation floue.

---

## 15 décembre 2025 — Le pipeline runtime devient cohérent (services + overlays)

La V2 prend une forme concrète : une boucle live qui assemble la capture, la vision et la résolution sans bricolage intermédiaire.
L’idée est simple : le code “pilote” ne fait plus que déclencher des services, et les artefacts (overlays) tombent automatiquement au bon endroit.

Le résultat le plus utile, c’est la traçabilité : chaque partie a ses dossiers (`temp/games/{id}/...`), et chaque overlay correspond à une étape du raisonnement.
Et côté exécution, je verrouille un principe de bon sens : la fin de session n’est appelée qu’une fois, par le pilote principal, avec un prompt avant fermeture du navigateur.

À partir de là, V2 n’est plus juste “une version plus propre”.
C’est une base stable sur laquelle je peux empiler des améliorations (pattern solver, extension navigateur) sans revenir au chaos.