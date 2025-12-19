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

---

## 16 décembre 2025 — Fusion des actions reducer + CSP dans GameLoopService

Le pipeline CSP fonctionne bien, mais les actions du reducer n'étaient pas exécutées en jeu. Le problème venait de `GameLoopService` qui ne récupérait que `solver_actions` et ignorait `reducer_actions`.

Correction apportée :
- Ajout de `solve_snapshot_with_reducer_actions` dans `StorageSolverService` pour construire les `SolverAction` depuis `reducer_safe/reducer_flags`
- Modification de `GameLoopService.execute_single_pass` pour fusionner reducer_actions + solver_actions
- Priorisation des actions déterministes (CLICK/FLAG) avant les GUESS
- Augmentation de `max_component_size` à 500 pour traiter des frontières plus grandes

Résultat : le bot exécute maintenant toutes les actions sûres (reducer + CSP) avant un éventuel guess. Les logs montrent bien les reducer_actions avec le tag `frontiere-reducer`.
La V2 verrouille donc un principe : l’information doit venir du canvas de manière la plus directe possible, et la vision doit rester déterministe.

---

## 16 décembre 2025 — Cohérence terminologique et alignement des SPECS

Aujourd'hui je consacre la journée à la cohérence terminologique et à l'alignement de toute la documentation sur un seul modèle didactique :

- **Sets storage** : `revealed_set / active_set / frontier_set` (plus de `unresolved`)
- **FocusLevel** : nomenclature explicite `TO_REDUCE / REDUCED` (ACTIVE) et `TO_PROCESS / PROCESSED` (FRONTIER)
- **TO_VISUALIZE** : écrit par le solver lorsqu’il annonce des cellules `SAFE` (amenées à changer), consommé ensuite pour cadrer la re-capture
- **ZoneDB** : index dérivé basé sur `zone_id` pour piloter le CSP uniquement sur les zones `TO_PROCESS`

- **Export_root unique** : tous les services reçoivent une seule racine de partie et ne reconstruisent plus de chemins
- **SPECS unifiées** : réécriture de `doc/SPECS/*` (S0, S1, s2, s3, s4, s5, ARCHITECTURE, PIPELINE) en style didactique
- **Dumb Solver Loop** : référence consolidée dans `doc/FOLLOW_PLAN/s44_dumb_solver_loop.md`

- **Performance terrain** : le bot fonctionne bien sans navigation auto/optimisation, mais autour de ~7000 de score la grille devient lente à résoudre → des optimisations lourdes restent nécessaires.

Ce travail de fond élimine les dernières ambiguïtés terminologiques et garantit que chaque couche parle le même langage. Le pipeline est maintenant entièrement lisible de la capture à l'action, avec des contrats explicites et une seule source de vérité pour les chemins.

La justification opérationnelle derrière ces choix est simple :

- Je veux **deux modes solver** : une réduction de frontière ultra-rapide (toujours) puis le CSP seulement si nécessaire.
- Je préfère une stratégie **SAFE-first** : au lieu de déclencher du progrès en “recliquant” des `ACTIVE`, je clique d’abord des cellules annoncées `SAFE` (inconnues) pour créer de l’information.
- Toutes les “astuces de clic” (double-clic SAFE, ménage local autour des actives) doivent rester dans s5 : le solver ne doit pas se transformer en exécuteur heuristique.

Avec l’architecture clarifiée, je peux enfin comparer proprement les pipelines et converger vers une solution qui marche seule : un solver CSP optimisé, autonome, dont la force vient d’un pré-traitement systématique (réduction frontière) plutôt que d’une hybridation floue.

---

## 15 décembre 2025 — Le pipeline runtime devient cohérent (services + overlays)

La V2 prend une forme concrète : une boucle live qui assemble la capture, la vision et la résolution sans bricolage intermédiaire.
L’idée est simple : le code “pilote” ne fait plus que déclencher des services, et les artefacts (overlays) tombent automatiquement au bon endroit.

Le résultat le plus utile, c’est la traçabilité : chaque partie a ses dossiers (`temp/games/{id}/...`), et chaque overlay correspond à une étape du raisonnement.
Et côté exécution, je verrouille un principe de bon sens : la fin de session n’est appelée qu’une fois, par le pilote principal, avec un prompt avant fermeture du navigateur.

À partir de là, V2 n’est plus juste “une version plus propre”.
C’est une base stable sur laquelle je peux empiler des améliorations (pattern solver, extension navigateur) sans revenir au chaos.

---

## État Actuel de V2 (déc 2025)

Le refactoring architectural a transformé V2 en une base solide :
- **Modules autonomes** : `lib/*` = logique pure, `services/*` = orchestration
- **Documentation unique** : `SPECS/` comme référence technique
- **Tests centralisés** : `tests/` (pas de dispersion)

V2 est maintenant prête pour les prochaines étapes :
- **V3-PERFORMANCES** : Optimisations algorithmiques
- **V4-FEATURES** : Nouvelles fonctionnalités
- **V5-TESTS** : Suite de tests automatisée